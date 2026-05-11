"""Agent-facing Screen Harness helpers."""

from __future__ import annotations

import importlib.util
import json
import atexit
import logging
import os
import shutil
import signal
import subprocess
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import IO


logger = logging.getLogger("screen_harness")

from .admin import ffmpeg_version, ffprobe_binary
from .captions import CaptionOutputs, generate_caption_assets
from .metadata import write_text_atomic
from .project import init_project
from .redact import scan_redactions as scan_recording_redactions
from .recorder import build_screen_record_command
from .render import DrawBox, StepPanel, concat_videos, create_intro_source, render_video
from .sop import generate_ai_sop as generate_ai_sop_assets
from .templates import DEFAULT_OUTRO_TITLE, get_template
from .timeline import TOKYO, Timeline
from .transcribe import transcribe_recording


@dataclass
class RuntimeState:
    root: Path
    recording_dir: Path | None = None
    timeline: Timeline | None = None
    started_at: float | None = None
    process: subprocess.Popen | None = None
    log_handle: IO[str] | None = None
    is_recording: bool = False
    screen_inventory: list | None = None  # cached probe_screens() result
    hud_process: subprocess.Popen | None = None  # optional HUD subprocess


_STATE = RuntimeState(root=Path.cwd())
_HUD_ATEXIT_REGISTERED = False
DEFAULT_HIGHLIGHT_COLOR = "blue@0.60"
DEFAULT_HIGHLIGHT_THICKNESS = 10

class RecordingStartFailed(RuntimeError):
    """Raised when FFmpeg exits with a non-zero code before recording is confirmed."""


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


def configure(root: Path) -> None:
    global _STATE
    _STATE = RuntimeState(root=Path(root))


def start_recording(
    name: str,
    *,
    screen: str | None = None,
    app: str | None = None,
    mic: str | None = None,
    intro: str | dict | None = None,
    template: str | None = None,
    capture_cursor: bool = True,
    capture_mouse_clicks: bool = True,
    region: tuple[int, int, int, int] | None = None,
    hud: bool = True,
) -> Path:
    init_project(_STATE.root)
    template_name = get_template(template).name
    recording_id = Timeline.recording_id(name)
    recording_dir = _STATE.root / "recordings" / recording_id
    recording_dir.mkdir(parents=True, exist_ok=True)
    raw = recording_dir / "raw.mp4"
    timeline = Timeline.create(
        path=recording_dir / "timeline.json",
        recording_id=recording_id,
        title=name,
        source_video="raw.mp4",
        intro=_intro_payload(intro),
    )
    ffmpeg_path = shutil.which("ffmpeg") or "ffmpeg"

    # Resolve the recording screen via smart selection.
    from .screens import ScreenProbeError, probe_screens, resolve_screen
    from dataclasses import asdict as _asdict

    if _STATE.screen_inventory is None:
        # No try/except — probe failures must propagate. Silently falling back
        # to AVFoundation index 0 is the camera-misuse bug D1 exists to
        # prevent (Codex bot finding P1 on PR #5, round 2).
        _STATE.screen_inventory = probe_screens(ffmpeg=ffmpeg_path)
        print("Available screens:")
        for s in _STATE.screen_inventory:
            main_marker = "  MAIN" if s.is_main else ""
            print(f"  [{s.av_index}] {s.av_name}  display_id={s.display_id} bounds={s.bounds}{main_marker}")

    _screen_spec: str | int | None = screen
    if _screen_spec is not None:
        try:
            _screen_spec = int(_screen_spec)
        except (ValueError, TypeError):
            pass
    # Likewise: resolve_screen failures (e.g. user passed a camera index, or
    # auto:<App> with no front window AND no main display) must raise.
    picked = resolve_screen(_screen_spec, app=app, ffmpeg=ffmpeg_path)
    print(f"Recording from: [{picked.device.av_index}] {picked.device.av_name}  ({picked.reason})")
    picked_screen_meta = _asdict(picked.device) | {"reason": picked.reason}
    screen_device_arg = picked.device

    # Validate region bounds before doing anything else.
    if region is not None:
        from .hud import validate_region_for_screen
        validate_region_for_screen(region, picked.device)

    # Determine if the HUD can and should be shown.
    # The HUD requires a pill anchor that fits entirely outside the crop rect.
    # Use pick_rec_pill_anchor to check: if it returns "none", no placement fits.
    hud_eligible = False
    if hud and region is not None:
        from .hud import pick_rec_pill_anchor, transform_region_to_appkit
        _crop_appkit = transform_region_to_appkit(region, picked.device)
        _screen_appkit = (*picked.device.appkit_origin, *picked.device.appkit_size)
        _pill_anchor = pick_rec_pill_anchor(_crop_appkit, _screen_appkit)
        if _pill_anchor == "none":
            print(
                "HUD disabled — crop region is too close to screen edges for the REC pill to fit outside.",
                flush=True,
            )
        else:
            hud_eligible = True
    elif hud and region is None:
        print(
            "Full-screen recording — HUD disabled; pass region= to enable",
            flush=True,
        )

    metadata = {
        "recording_id": recording_id,
        "name": name,
        "created_at": timeline.data["created_at"],
        "recording_started_at": timeline.data["created_at"],
        "recording_stopped_at": None,
        "duration": None,
        "status": "recording",
        "raw_video": "raw.mp4",
        "ffmpeg_path": ffmpeg_path,
        "ffmpeg_version": _safe_ffmpeg_version(ffmpeg_path),
        "canvas": None,
        "render_template": template_name,
        "capture_cursor": capture_cursor,
        "capture_mouse_clicks": capture_mouse_clicks,
        "region": list(region) if region else None,
        "picked_screen": picked_screen_meta,
        "hud_active": False,  # updated below if HUD starts
        "error": None,
    }
    _write_json(recording_dir / "metadata.json", metadata)
    log_handle = (recording_dir / "ffmpeg.log").open("w")
    cmd = build_screen_record_command(
        raw,
        duration=None,
        screen_device=screen_device_arg,
        audio_index=mic,
        capture_cursor=capture_cursor,
        capture_mouse_clicks=capture_mouse_clicks,
        region=region,
    )
    # FFmpeg stderr is captured separately so we can watch for the
    # "AVFoundation capture started" line to get an accurate started_at.
    ffmpeg_stderr_pipe = subprocess.PIPE

    # `start_new_session=True` puts FFmpeg (and any AVFoundation helper
    # subprocesses it forks) into a fresh process group so we can SIGTERM the
    # whole tree on stop/abort instead of leaving zombies.
    process = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=log_handle,
        stderr=ffmpeg_stderr_pipe,
        start_new_session=True,
    )

    # Populate runtime state IMMEDIATELY after Popen so any KeyboardInterrupt
    # or BaseException during the ~5 s FFmpeg-start wait or HUD launch can be
    # cleaned up by `abort_active_recording()`.  Previously these fields were
    # only set *after* both waits completed, so an interrupt during the wait
    # window orphaned FFmpeg recording in the background (Codex P2 round 4).
    _STATE.recording_dir = recording_dir
    _STATE.timeline = timeline
    _STATE.process = process
    _STATE.log_handle = log_handle
    _STATE.is_recording = True
    _STATE.hud_process = None
    _STATE.started_at = None

    try:
        # Wait for FFmpeg to confirm capture has started (up to 5 s).
        started_at = _wait_for_ffmpeg_start(process, log_handle, raw_path=raw, timeout=5.0)
        _STATE.started_at = started_at

        # Launch HUD subprocess (best-effort; recording must not fail if HUD fails).
        hud_proc: subprocess.Popen | None = None
        if hud_eligible:
            hud_proc = _launch_hud_subprocess(
                screen_device=picked.device,
                region=region,
                started_at=started_at,
            )
            if hud_proc is not None:
                metadata["hud_active"] = True
                _write_json(recording_dir / "metadata.json", metadata)
        _STATE.hud_process = hud_proc
    except BaseException:
        _cleanup_failed_start(process, log_handle, hud_proc=_STATE.hud_process)
        raise

    # Register HUD teardown once per process (idempotent guard).
    global _HUD_ATEXIT_REGISTERED
    if not _HUD_ATEXIT_REGISTERED:
        atexit.register(_atexit_hud_cleanup)
        _HUD_ATEXIT_REGISTERED = True

    return recording_dir


def _signal_process_group(process: subprocess.Popen, sig: int) -> None:
    """Send `sig` to the process's whole group; fall back to the leader on macOS edge cases."""
    try:
        os.killpg(os.getpgid(process.pid), sig)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            process.send_signal(sig)
        except (ProcessLookupError, OSError):
            pass


def _cleanup_failed_start(
    process: subprocess.Popen,
    log_handle: "IO[str] | None",
    *,
    hud_proc: "subprocess.Popen | None" = None,
) -> None:
    """Best-effort teardown after start_recording fails mid-startup.

    Kills the FFmpeg process group, closes the log handle, terminates any
    partial HUD subprocess, and resets _STATE to a clean (not-recording)
    state.  All sub-operations are wrapped individually so a failure in one
    step does not prevent the others from running.
    """
    try:
        _signal_process_group(process, signal.SIGTERM)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _signal_process_group(process, signal.SIGKILL)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
    except Exception:
        pass
    try:
        if log_handle is not None:
            log_handle.close()
    except Exception:
        pass
    if hud_proc is not None:
        try:
            hud_proc.terminate()
        except Exception:
            pass
    _STATE.is_recording = False
    _STATE.process = None
    _STATE.log_handle = None
    _STATE.recording_dir = None
    _STATE.timeline = None
    _STATE.started_at = None
    _STATE.hud_process = None


# FFmpeg stderr lines that confirm avfoundation capture has begun.
# Intentionally narrow: b"avfoundation" (lower-case) was removed because it
# also matches FFmpeg error lines like "avfoundation: failed to access screen",
# producing false positives. b"frame=" / b"fps=" were removed because they
# appear only after encoding starts (too late) and can appear in error context
# too. b"Stream #0" is added because FFmpeg prints it when the output stream is
# opened, which reliably indicates capture has begun.
_FFMPEG_STARTED_PATTERNS = (
    b"AVFoundation capture started",
    b"Stream #0",
)


def _wait_for_ffmpeg_start(
    process: subprocess.Popen,
    log_handle: "IO[str]",
    *,
    raw_path: Path,
    timeout: float = 5.0,
) -> float:
    """Poll until recording is confirmed, FFmpeg crashes, or timeout expires.

    Verification priority:
    1. HARD WIN  — raw_path exists and its size exceeds 1024 bytes.  The file
       is actively being written; capture is confirmed.  Returns monotonic time.
    2. HARD FAIL — process.poll() is not None before the file grows.  FFmpeg
       died during startup.  Raises RecordingStartFailed with the return code
       and the last ~300 chars of stderr if available.
    3. SOFT WIN  — a stderr pattern from _FFMPEG_STARTED_PATTERNS matched.
       Returns confirmed_at[0] only when no hard-fail has occurred.
    4. TIMEOUT   — deadline passed with no signal.  Logs a warning and returns
       popen_time (the time captured before the loop — not now+timeout) so that
       duration metadata stays anchored to the actual Popen call.

    Stderr bytes are forwarded to *log_handle* so ffmpeg.log remains complete.
    """
    import threading

    # Capture popen_time BEFORE the wait loop so the timeout fallback returns
    # the actual launch time, not now+timeout (PR #7 Codex P2 round 2).
    popen_time = time.monotonic()
    deadline = popen_time + timeout
    confirmed_at: list[float] = []

    stderr_pipe = getattr(process, "stderr", None)

    if stderr_pipe is not None:
        # Read FFmpeg stderr in a background thread so we don't block the poll
        # loop waiting for lines that may never arrive.
        def _reader():
            try:
                for raw_line in stderr_pipe:
                    if log_handle:
                        try:
                            log_handle.write(raw_line.decode("utf-8", errors="replace"))
                            log_handle.flush()
                        except (OSError, ValueError):
                            pass
                    if not confirmed_at:
                        for pat in _FFMPEG_STARTED_PATTERNS:
                            if pat in raw_line:
                                confirmed_at.append(time.monotonic())
                                break
            except Exception:
                pass

        t = threading.Thread(target=_reader, daemon=True)
        t.start()

    # Main poll loop — 50 ms cadence.
    while time.monotonic() < deadline:
        # HARD WIN: output file is growing.
        if raw_path.exists() and raw_path.stat().st_size > 1024:
            return time.monotonic()

        # HARD FAIL: process exited before any bytes were written.
        _poll = getattr(process, "poll", None)
        if _poll is not None and _poll() is not None:
            stderr_tail = ""
            if stderr_pipe is not None:
                try:
                    chunk = stderr_pipe.read(300)
                    if chunk:
                        stderr_tail = f" stderr: {chunk.decode('utf-8', errors='replace')[-300:]}"
                except Exception:
                    pass
            raise RecordingStartFailed(
                f"FFmpeg exited rc={process.returncode} during startup{stderr_tail}"
            )

        # SOFT WIN: stderr pattern matched (fallback; less reliable than file growth).
        if confirmed_at:
            return confirmed_at[0]

        time.sleep(0.05)

    # TIMEOUT: no signal received within the deadline.
    if not confirmed_at:
        logger.warning(
            "FFmpeg capture start not confirmed within %.1fs; "
            "using Popen time as started_at",
            timeout,
        )
        return popen_time

    return confirmed_at[0]


def _launch_hud_subprocess(
    *,
    screen_device: "object",
    region: tuple[int, int, int, int],
    started_at: float,
) -> "subprocess.Popen | None":
    """Launch ``python -m screen_harness.hud`` and send the start command.

    Returns the Popen object on success, or None if the subprocess cannot
    be started (recording must not fail because the HUD failed).
    """
    import sys as _sys
    from dataclasses import asdict as _asdict

    try:
        hud_proc = subprocess.Popen(
            [_sys.executable, "-m", "screen_harness.hud"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except OSError as exc:
        logger.warning("HUD subprocess could not be launched (%s); recording continues without HUD.", exc)
        return None

    try:
        screen_dict = _asdict(screen_device)
        # bounds is a tuple — JSON needs a list
        screen_dict["bounds"] = list(screen_dict["bounds"])
        start_cmd = json.dumps({
            "cmd": "start",
            "screen": screen_dict,
            "region": list(region),
            "started_at": started_at,
        }) + "\n"
        if hud_proc.stdin is None:
            raise OSError("HUD subprocess has no stdin pipe")
        hud_proc.stdin.write(start_cmd)
        hud_proc.stdin.flush()
    except (OSError, BrokenPipeError) as exc:
        logger.warning("HUD start command failed (%s); recording continues without HUD.", exc)
        try:
            hud_proc.kill()
            hud_proc.wait(timeout=1)
        except Exception:
            pass
        return None

    # Codex P2 round 2 (PR #7): the child may have exited during AppKit
    # import (e.g. missing/broken PyObjC) even though stdin.write succeeded
    # because the pipe buffer absorbs the write before the kernel notices
    # the dead reader.  Give the child a short window to crash, then
    # poll() and treat early-exit as a launch failure so `hud_active` in
    # metadata.json reflects reality.
    time.sleep(0.15)
    if hud_proc.poll() is not None:
        rc = hud_proc.returncode
        try:
            stderr_tail = (hud_proc.stderr.read() or "").strip()[-300:] if hud_proc.stderr else ""
        except Exception:
            stderr_tail = ""
        logger.warning(
            "HUD subprocess exited during startup (rc=%s); recording continues without HUD. stderr: %s",
            rc, stderr_tail,
        )
        return None

    return hud_proc


def _stop_hud_subprocess(hud_proc: "subprocess.Popen | None") -> None:
    """Close HUD subprocess stdin → child sees EOF → terminates within 200 ms."""
    if hud_proc is None:
        return
    try:
        if hud_proc.stdin and not hud_proc.stdin.closed:
            hud_proc.stdin.close()
    except (OSError, BrokenPipeError):
        pass
    try:
        hud_proc.wait(timeout=0.5)
    except subprocess.TimeoutExpired:
        try:
            hud_proc.kill()
            hud_proc.wait(timeout=0.5)
        except Exception:
            pass
    except Exception:
        pass


def _atexit_hud_cleanup() -> None:
    """atexit handler — tears down HUD if the process exits without stop_recording()."""
    _stop_hud_subprocess(_STATE.hud_process)
    _STATE.hud_process = None


def stop_recording() -> Path:
    if not _STATE.is_recording or not _STATE.process or not _STATE.recording_dir:
        raise RuntimeError("no active recording")
    process = _STATE.process
    recording_dir = _STATE.recording_dir
    log_handle = _STATE.log_handle
    hud_proc = _STATE.hud_process
    try:
        # Tear down HUD first (closes stdin → child sees EOF → exits within 200 ms).
        _stop_hud_subprocess(hud_proc)

        # Politely ask FFmpeg to stop. Any I/O error here just falls through
        # to the wait/terminate/kill cascade below — we never want a stdin
        # hiccup to leave the process or log handle leaked.
        if process.stdin:
            try:
                process.stdin.write(b"q")
                process.stdin.flush()
            except (BrokenPipeError, OSError, ValueError):
                pass
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            _signal_process_group(process, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                _signal_process_group(process, signal.SIGKILL)
                process.wait(timeout=5)
        duration = _elapsed()
        metadata_path = recording_dir / "metadata.json"
        metadata = json.loads(metadata_path.read_text())
        metadata["recording_stopped_at"] = datetime.now(TOKYO).isoformat()
        metadata["duration"] = round(duration, 3)
        metadata["status"] = "stopped" if process.returncode == 0 else "error"
        metadata["error"] = None if process.returncode == 0 else f"ffmpeg exited {process.returncode}"
        metadata["canvas"] = _probe_canvas(recording_dir / "raw.mp4")
        _write_json(metadata_path, metadata)
        return recording_dir
    finally:
        # Always release the log handle and recording flag, even when the
        # metadata write or wait cascade raises — otherwise a single failed
        # stop leaves the runtime stuck claiming a recording is live.
        if log_handle is not None:
            try:
                log_handle.close()
            except OSError:
                pass
        _STATE.is_recording = False
        _STATE.process = None
        _STATE.log_handle = None
        _STATE.hud_process = None


def abort_active_recording() -> None:
    if not _STATE.is_recording or not _STATE.process:
        return
    process = _STATE.process
    log_handle = _STATE.log_handle
    recording_dir = _STATE.recording_dir
    hud_proc = _STATE.hud_process
    try:
        # Tear down HUD first so the pill disappears immediately.
        _stop_hud_subprocess(hud_proc)

        # The outer finally below always nulls runtime state, so a metadata
        # write or log close that raises here cannot leave the harness wedged
        # into thinking a recording is still live — same anti-wedge guarantee
        # `stop_recording` provides. The inner try below only handles the
        # SIGTERM → SIGKILL escalation; everything else (log close, metadata
        # write) is intentionally bare so its exceptions surface to the caller.
        try:
            _signal_process_group(process, signal.SIGTERM)
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _signal_process_group(process, signal.SIGKILL)
            process.wait(timeout=5)
        if log_handle is not None:
            try:
                log_handle.close()
            except OSError:
                pass
        if recording_dir is not None:
            metadata_path = recording_dir / "metadata.json"
            if metadata_path.exists():
                metadata = json.loads(metadata_path.read_text())
                metadata["recording_stopped_at"] = datetime.now(TOKYO).isoformat()
                metadata["duration"] = round(_elapsed(), 3)
                metadata["status"] = "aborted"
                metadata["error"] = "script exited before stop_recording()"
                _write_json(metadata_path, metadata)
    finally:
        _STATE.is_recording = False
        _STATE.process = None
        _STATE.log_handle = None
        _STATE.hud_process = None


def wait(seconds: float = 1.0) -> None:
    time.sleep(seconds)


def wait_for_user(message: str = "Press Enter to continue") -> None:
    input(f"{message}\n")


def intro(title: str, *, subtitle: str | None = None, countdown: int = 5) -> None:
    timeline = _timeline()
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
    timeline = _timeline()
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
    _timeline().add_event("chapter", t=_event_time(t), title=title)


def step(title: str, *, note: str | None = None, number: int | None = None, t: float | None = None) -> None:
    _timeline().add_event("step", t=_event_time(t), title=title, note=note, number=number)


def caption(text: str, *, duration: float | None = None, t: float | None = None) -> None:
    _timeline().add_event("caption", t=_event_time(t), text=text, duration=duration)


def click(x: int, y: int, *, label: str | None = None, t: float | None = None) -> None:
    _timeline().add_event("click", t=_event_time(t), x=x, y=y, label=label)


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
    _timeline().add_event("highlight", t=_event_time(None), rect=[x, y, w, h], text=text, duration=duration, color=color, thickness=thickness)


def redact_region(x: int, y: int, w: int, h: int, *, reason: str | None = None, duration: float | None = None) -> None:
    """Black-fill a rectangle. Coordinates follow the same recorded-frame
    convention as `highlight_region`."""
    _timeline().add_event("redact", t=_event_time(None), rect=[x, y, w, h], reason=reason, duration=duration)


def generate_sop_captions(recording_dir: Path | None = None, *, template: str | None = None):
    return generate_caption_assets(recording_dir or _recording_dir(), template=template)


def generate_ai_sop(recording_dir: Path | None = None):
    return generate_ai_sop_assets(recording_dir or _recording_dir())


def generate_markdown_sop(recording_dir: Path | None = None) -> Path:
    return generate_caption_assets(recording_dir or _recording_dir()).markdown


def transcribe(recording_dir: Path | None = None):
    return transcribe_recording(recording_dir or _recording_dir())


def scan_redactions(recording_dir: Path | None = None):
    return scan_recording_redactions(recording_dir or _recording_dir())


def render(recording_dir: Path | None = None, *, template: str | None = None) -> Path:
    if _STATE.is_recording:
        raise RuntimeError("call stop_recording() before render()")
    directory = Path(recording_dir) if recording_dir else _recording_dir()
    template_name = get_template(template or _metadata_template(directory)).name
    raw = directory / "raw.mp4"
    if not raw.exists():
        raise FileNotFoundError(f"raw recording not found: {raw}")
    canvas = _render_canvas(directory, raw)
    canvas_size = (int(canvas["width"]), int(canvas["height"]))
    outputs = generate_caption_assets(directory, template=template_name, canvas=canvas_size)
    final = directory / "final.mp4"
    timeline = Timeline.load(directory / "timeline.json")
    template_obj = get_template(template_name)
    panel = _build_step_panel(template_obj, timeline.data, canvas_size)
    has_intro = bool(outputs.intro_ass and template_obj.intro_duration(timeline.data) > 0)
    has_outro = bool(
        outputs.outro_ass and template_obj.outro_duration(timeline.data) > 0
    )
    has_audio = _probe_audio(raw)
    if has_intro or has_outro:
        clips: list[Path] = []
        if has_intro:
            intro_video = _render_card_clip(
                directory,
                source_name="intro-source.mp4",
                clip_name="intro.mp4",
                ass=outputs.intro_ass,
                canvas=canvas,
                duration=template_obj.intro_duration(timeline.data),
                background_color=template_obj.intro_background_color(timeline.data),
                with_audio=has_audio,
            )
            clips.append(intro_video)
        main_video = directory / "main.mp4"
        result = render_video(raw, outputs.ass, main_video, boxes=_drawboxes(timeline.data, canvas=canvas_size), step_panel=panel)
        if result.returncode != 0:
            raise RuntimeError(result.stdout)
        clips.append(main_video)
        if has_outro:
            outro_video = _render_card_clip(
                directory,
                source_name="outro-source.mp4",
                clip_name="outro.mp4",
                ass=outputs.outro_ass,
                canvas=canvas,
                duration=template_obj.outro_duration(timeline.data),
                background_color=template_obj.outro_background_color(timeline.data),
                with_audio=has_audio,
            )
            clips.append(outro_video)
        result = concat_videos(*clips, final, audio=has_audio)
    else:
        result = render_video(raw, outputs.ass, final, boxes=_drawboxes(timeline.data, canvas=canvas_size), step_panel=panel)
    if result.returncode != 0:
        raise RuntimeError(result.stdout)
    _write_render_metadata(directory, template_name, final)
    return final


def _render_card_clip(
    directory: Path,
    *,
    source_name: str,
    clip_name: str,
    ass: Path,
    canvas: dict,
    duration: float,
    background_color: str,
    with_audio: bool = False,
) -> Path:
    source = directory / source_name
    output = directory / clip_name
    result = create_intro_source(
        source,
        width=canvas["width"],
        height=canvas["height"],
        fps=canvas["fps"],
        duration=duration,
        background_color=background_color,
        with_audio=with_audio,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stdout)
    result = render_video(source, ass, output)
    if result.returncode != 0:
        raise RuntimeError(result.stdout)
    return output


def _build_step_panel(template_obj, data: dict, canvas: tuple[int, int]):
    rect = template_obj.step_panel_rect(canvas)
    if rect is None:
        return None
    intervals = template_obj.step_intervals(data)
    if not intervals:
        return None
    x, y, w, h = rect
    return StepPanel(x=x, y=y, width=w, height=h, intervals=intervals)


def load_agent_helpers(workspace: Path, namespace: dict) -> None:
    helper_file = Path(workspace) / "agent_helpers.py"
    if not helper_file.exists():
        return
    spec = importlib.util.spec_from_file_location("screen_harness_agent_helpers", helper_file)
    if not spec or not spec.loader:
        return
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name, value in vars(module).items():
        if not name.startswith("_"):
            namespace[name] = value


def _timeline() -> Timeline:
    if not _STATE.timeline:
        raise RuntimeError("start_recording() must be called first")
    return _STATE.timeline


def _recording_dir() -> Path:
    if not _STATE.recording_dir:
        raise RuntimeError("no recording directory is active")
    return _STATE.recording_dir


def _event_time(t: float | None) -> float:
    return _elapsed() if t is None else float(t)


def _elapsed() -> float:
    if _STATE.started_at is None:
        return 0.0
    return time.monotonic() - _STATE.started_at


def _drawboxes(data: dict, canvas: tuple[int, int] | None = None) -> list[DrawBox]:
    boxes: list[DrawBox] = []
    for event in data.get("events", []):
        if event["type"] == "highlight":
            x, y, w, h = event["rect"]
            _warn_if_outside_canvas("highlight", event.get("text"), x, y, w, h, canvas)
            boxes.append(
                DrawBox(
                    x=x,
                    y=y,
                    width=w,
                    height=h,
                    start=event["t"],
                    duration=event.get("duration", 3.0),
                    color=event.get("color", DEFAULT_HIGHLIGHT_COLOR),
                    thickness=event.get("thickness", DEFAULT_HIGHLIGHT_THICKNESS),
                )
            )
        elif event["type"] == "redact":
            x, y, w, h = event["rect"]
            _warn_if_outside_canvas("redact", event.get("reason"), x, y, w, h, canvas)
            boxes.append(DrawBox(x=x, y=y, width=w, height=h, start=event["t"], duration=event.get("duration"), color="black@0.85", thickness="fill"))
        elif event["type"] == "click":
            cx, cy = event["x"], event["y"]
            if canvas is not None:
                cw, ch = canvas
                # Pixel coordinates are 0-indexed: valid range is [0, cw) × [0, ch).
                # A click at (cw, ch) is one pixel past the canvas — warn.
                if not (0 <= cx < cw and 0 <= cy < ch):
                    logger.warning(
                        "click event at (%d, %d) is outside canvas %dx%d — coordinates "
                        "must be relative to the recorded frame, not the screen "
                        "(see metadata.region for the screen origin of this recording).",
                        cx, cy, cw, ch,
                    )
            boxes.append(DrawBox(x=max(0, cx - 18), y=max(0, cy - 18), width=36, height=36, start=event["t"], duration=1.0, color="red@0.45"))
    return boxes


def _warn_if_outside_canvas(kind: str, label: str | None, x: int, y: int, w: int, h: int, canvas: tuple[int, int] | None) -> None:
    if canvas is None:
        return
    cw, ch = canvas
    if x < 0 or y < 0 or x + w > cw or y + h > ch:
        logger.warning(
            "%s rect (%s) at (%d,%d,%d,%d) extends outside canvas %dx%d — "
            "coordinates must be authored against the recorded frame; if you "
            "captured with region=, subtract the region origin (see metadata.region).",
            kind, label or "<unlabeled>", x, y, w, h, cw, ch,
        )


def _metadata_template(directory: Path) -> str | None:
    metadata_path = Path(directory) / "metadata.json"
    if not metadata_path.exists():
        return None
    try:
        return json.loads(metadata_path.read_text()).get("render_template")
    except json.JSONDecodeError:
        return None


def _intro_payload(value: str | dict | None) -> dict | None:
    if value is None:
        return None
    if isinstance(value, str):
        return {"title": value, "countdown": 5}
    return dict(value)


def _render_canvas(directory: Path, raw: Path) -> dict:
    """Resolve canvas size+fps for the recording.

    Prefers the canvas block written into `metadata.json` by `stop_recording`
    (which captured it from ffprobe at recording time). Falls back to a fresh
    ffprobe of the raw clip. Raises `RuntimeError` if neither source yields a
    valid canvas — silently defaulting to (1920, 1080, 30) would mis-align
    every overlay coordinate when the actual raw is a cropped region (e.g.
    Safari at 1920x960 from `region=`).
    """
    metadata_path = Path(directory) / "metadata.json"
    canvas: dict | None = None
    if metadata_path.exists():
        try:
            metadata_canvas = json.loads(metadata_path.read_text()).get("canvas")
        except json.JSONDecodeError:
            metadata_canvas = None
        if isinstance(metadata_canvas, dict) and metadata_canvas.get("width") and metadata_canvas.get("height"):
            canvas = metadata_canvas
    if canvas is None:
        canvas = _probe_canvas(raw)
    if not canvas or not canvas.get("width") or not canvas.get("height"):
        raise RuntimeError(
            f"could not determine canvas dimensions for {raw}; ensure ffprobe is "
            "available or that metadata.json carries a populated 'canvas' block"
        )
    return {
        "width": int(canvas["width"]),
        "height": int(canvas["height"]),
        "fps": float(canvas.get("fps") or 30.0),
    }


def _probe_audio(path: Path) -> bool:
    """Return True if `path` carries at least one audio stream.

    Returns False on any probe failure (missing ffprobe, missing file,
    unreadable container) and emits a warning so a user whose recording
    has audio doesn't silently lose it. The caller (`render`) treats the
    return value as the only signal for audio passthrough — explicitly
    document that behavior rather than inferring it.
    """
    if not path.exists():
        return False
    try:
        result = subprocess.run(
            [
                ffprobe_binary(),
                "-v",
                "error",
                "-select_streams",
                "a",
                "-show_entries",
                "stream=codec_type",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
    except OSError as exc:
        logger.warning(
            "ffprobe unavailable while probing %s for audio (%s); audio passthrough "
            "will be skipped — install ffprobe or set SCREEN_HARNESS_FFPROBE to enable it.",
            path, exc,
        )
        return False
    if result.returncode != 0:
        logger.warning(
            "ffprobe returned %d while probing %s for audio; treating as no audio. "
            "stderr: %s",
            result.returncode, path, result.stdout.strip()[:200],
        )
        return False
    return "audio" in result.stdout


def _write_render_metadata(directory: Path, template_name: str, final: Path) -> None:
    metadata_path = Path(directory) / "metadata.json"
    if metadata_path.exists():
        try:
            metadata = json.loads(metadata_path.read_text())
        except json.JSONDecodeError:
            metadata = {}
    else:
        metadata = {}
    metadata["render_template"] = template_name
    metadata["rendered_video"] = str(Path(final).name)
    metadata["rendered_at"] = datetime.now(TOKYO).isoformat()
    _write_json(metadata_path, metadata)


def _write_json(path: Path, data: dict) -> None:
    write_text_atomic(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def _safe_ffmpeg_version(ffmpeg_path: str) -> str | None:
    try:
        return ffmpeg_version(ffmpeg_path)
    except (OSError, subprocess.SubprocessError):
        return None


def _probe_canvas(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        result = subprocess.run(
            [
                ffprobe_binary(),
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height,r_frame_rate,duration",
                "-of",
                "json",
                str(path),
            ],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    try:
        streams = json.loads(result.stdout).get("streams", [])
    except json.JSONDecodeError:
        return None
    if not streams:
        return None
    stream = streams[0]
    fps = _parse_rate(stream.get("r_frame_rate"))
    return {
        "width": int(stream["width"]) if "width" in stream else None,
        "height": int(stream["height"]) if "height" in stream else None,
        "fps": fps,
        "duration": float(stream["duration"]) if stream.get("duration") else None,
    }


def _parse_rate(value: str | None) -> float | None:
    if not value:
        return None
    if "/" in value:
        num, den = value.split("/", 1)
        denominator = float(den)
        return None if denominator == 0 else float(num) / denominator
    return float(value)
