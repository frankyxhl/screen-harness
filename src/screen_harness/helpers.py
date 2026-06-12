"""Agent-facing Screen Harness helpers.

This module is the public facade: the `screen-harness -c` script namespace is
built from its ``__all__``, and `run.py` drives everything through it. The
implementation lives in focused modules:

- :mod:`screen_harness.runtime`        — shared `_STATE` singleton + accessors
- :mod:`screen_harness.recording`      — start/stop/abort lifecycle
- :mod:`screen_harness.hud_supervisor` — HUD subprocess management
- :mod:`screen_harness.rendering`      — render orchestration
- :mod:`screen_harness.probing`        — ffmpeg/ffprobe introspection

The timeline-event script API (``intro``/``step``/``caption``/…) is defined
here directly: each helper is a thin write into the active timeline.
"""

from __future__ import annotations

import time
import unicodedata
from pathlib import Path

from . import runtime
from .captions import generate_caption_assets
from .recording import (
    RecordingStartFailed as RecordingStartFailed,
    abort_active_recording as abort_active_recording,
    start_recording as start_recording,
    stop_recording as stop_recording,
)
from .redact import scan_redactions as scan_recording_redactions
from .rendering import render as render
from .runtime import (
    RuntimeState as RuntimeState,
    configure as configure,
    load_agent_helpers as load_agent_helpers,
)
from .sop import generate_ai_sop as generate_ai_sop_assets
from .templates import DEFAULT_OUTRO_TITLE
from .transcribe import transcribe_recording

__all__ = [
    "RecordingStartFailed",
    "start_recording",
    "stop_recording",
    "wait",
    "wait_for_user",
    "intro",
    "outro",
    "chapter",
    "step",
    "caption",
    "click",
    "highlight_region",
    "redact_region",
    "generate_sop_captions",
    "generate_ai_sop",
    "generate_markdown_sop",
    "transcribe",
    "scan_redactions",
    "render",
]

def wait(seconds: float = 1.0) -> None:
    time.sleep(seconds)


def wait_for_user(message: str = "Press Enter to continue") -> None:
    input(f"{message}\n")


def intro(title: str, *, subtitle: str | None = None, countdown: int = 5) -> None:
    timeline = runtime._timeline()
    timeline.data["intro"] = {"title": title, "countdown": int(countdown)}
    if subtitle is not None:
        timeline.data["intro"]["subtitle"] = subtitle
    timeline.save()


_MAX_OUTRO_TEXT_LEN = 200


def outro(
    title: str = DEFAULT_OUTRO_TITLE,
    *,
    subtitle: str | None = None,
    url: str | None = None,
    duration: float = 4.0,
) -> None:
    """Hold a branded end card after the main recording.

    The outro is rendered against a solid charcoal background by the training
    template; it shows a small wordmark, a centered title, an optional
    subtitle, and the project URL in the accent color. Text fields are
    bounded at 200 characters to keep the card legible — anything longer
    is rejected so a stray multi-paragraph URL can't blow out the layout.
    """
    timeline = runtime._timeline()
    duration_value = float(duration)
    if duration_value <= 0:
        raise ValueError(f"outro duration must be positive, got {duration!r}")
    payload: dict = {"title": _check_outro_text("title", title), "duration": duration_value}
    if subtitle is not None:
        payload["subtitle"] = _check_outro_text("subtitle", subtitle)
    if url is not None:
        payload["url"] = _check_outro_text("url", url)
    timeline.data["outro"] = payload
    timeline.save()


def _check_outro_text(field: str, value: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"outro.{field} must be a string, got {type(value).__name__}")
    if len(value) > _MAX_OUTRO_TEXT_LEN:
        raise ValueError(f"outro.{field} exceeds {_MAX_OUTRO_TEXT_LEN} chars (got {len(value)})")
    # Reject every Unicode control category (Cc) — covers C0 (0x00-0x1F), DEL
    # (0x7F), and C1 (0x80-0x9F). `\n` is the one whitelisted exception so
    # multi-line subtitles still work.
    for ch in value:
        if ch == "\n":
            continue
        if unicodedata.category(ch) == "Cc":
            raise ValueError(f"outro.{field} contains control characters")
    return value


def chapter(title: str, *, t: float | None = None) -> None:
    runtime._timeline().add_event("chapter", t=runtime._event_time(t), title=title)


def step(title: str, *, note: str | None = None, number: int | None = None, t: float | None = None) -> None:
    runtime._timeline().add_event("step", t=runtime._event_time(t), title=title, note=note, number=number)


def caption(text: str, *, duration: float | None = None, t: float | None = None) -> None:
    runtime._timeline().add_event("caption", t=runtime._event_time(t), text=text, duration=duration)


def click(x: int, y: int, *, label: str | None = None, t: float | None = None) -> None:
    runtime._timeline().add_event("click", t=runtime._event_time(t), x=x, y=y, label=label)


def highlight_region(
    x: int,
    y: int,
    w: int,
    h: int,
    *,
    text: str | None = None,
    duration: float = 3.0,
    color: str | None = None,
    thickness: int | str | None = None,
) -> None:
    """Draw a colored stroke around a rectangle in the recording.

    Coordinates are **relative to the recorded frame**, not the screen. When
    `start_recording(region=(rx, ry, w, h))` was used, the recorded frame's
    origin is the cropped region's top-left, so overlay coordinates must be
    authored against the *cropped* canvas — not the macOS screen.

    Out-of-canvas rectangles are accepted (they may be intentional bleed) but
    `helpers.render` will log a warning.
    """
    runtime._timeline().add_event("highlight", t=runtime._event_time(None), rect=[x, y, w, h], text=text, duration=duration, color=color, thickness=thickness)


def redact_region(x: int, y: int, w: int, h: int, *, reason: str | None = None, duration: float | None = None) -> None:
    """Black-fill a rectangle. Coordinates follow the same recorded-frame
    convention as `highlight_region`."""
    runtime._timeline().add_event("redact", t=runtime._event_time(None), rect=[x, y, w, h], reason=reason, duration=duration)


def generate_sop_captions(recording_dir: Path | None = None, *, template: str | None = None):
    return generate_caption_assets(recording_dir or runtime._recording_dir(), template=template)


def generate_ai_sop(recording_dir: Path | None = None):
    return generate_ai_sop_assets(recording_dir or runtime._recording_dir())


def generate_markdown_sop(recording_dir: Path | None = None) -> Path:
    return generate_caption_assets(recording_dir or runtime._recording_dir()).markdown


def transcribe(recording_dir: Path | None = None):
    return transcribe_recording(recording_dir or runtime._recording_dir())


def scan_redactions(recording_dir: Path | None = None):
    return scan_recording_redactions(recording_dir or runtime._recording_dir())
