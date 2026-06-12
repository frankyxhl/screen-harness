"""Render orchestration: timeline + raw.mp4 → final.mp4 with overlays."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from . import probing, runtime
from .captions import generate_caption_assets
from .render import DrawBox, StepPanel, concat_videos, create_intro_source, render_video
from .templates import get_template
from .timeline import Timeline, local_now

logger = logging.getLogger("screen_harness")

DEFAULT_HIGHLIGHT_COLOR = "blue@0.60"
DEFAULT_HIGHLIGHT_THICKNESS = 10


def render(recording_dir: Path | None = None, *, template: str | None = None) -> Path:
    if runtime._STATE.is_recording:
        raise RuntimeError("call stop_recording() before render()")
    directory = Path(recording_dir) if recording_dir else runtime._recording_dir()
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
    has_audio = probing._probe_audio(raw)
    if has_intro or has_outro:
        if not canvas.get("fps"):
            raise RuntimeError(
                f"could not determine frame rate for {raw}; intro/outro card "
                "clips are generated at the canvas rate — ensure ffprobe is "
                "available or that metadata.json carries a 'canvas' block "
                "with 'fps'"
            )
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


def _render_canvas(directory: Path, raw: Path) -> dict:
    """Resolve canvas size+fps for the recording.

    Prefers the canvas block written into `metadata.json` by `stop_recording`
    (which captured it from ffprobe at recording time). Falls back to a fresh
    ffprobe of the raw clip. Raises `RuntimeError` if neither source yields a
    valid canvas — silently defaulting to (1920, 1080, 30) would mis-align
    every overlay coordinate when the actual raw is a cropped region (e.g.
    Safari at 1920x960 from `region=`). fps is never guessed either — a
    guessed 30 would mis-time intro/outro cards against a 24/60 fps raw clip
    — but an unresolvable rate returns None rather than raising, because only
    the card-clip path consumes it; render() raises at that branch.
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
        canvas = probing._probe_canvas(raw)
    if not canvas or not canvas.get("width") or not canvas.get("height"):
        raise RuntimeError(
            f"could not determine canvas dimensions for {raw}; ensure ffprobe is "
            "available or that metadata.json carries a populated 'canvas' block"
        )
    if not canvas.get("fps"):
        # metadata canvas without fps (older recordings) — the raw clip
        # itself knows the real rate.
        probed = probing._probe_canvas(raw)
        if probed and probed.get("fps"):
            canvas = {**canvas, "fps": probed["fps"]}
    return {
        "width": int(canvas["width"]),
        "height": int(canvas["height"]),
        # None when unresolvable — only intro/outro card clips consume the
        # rate, so render() raises there instead of blocking main-only
        # renders (Codex P2 on PR #22).
        "fps": float(canvas["fps"]) if canvas.get("fps") else None,
    }


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
    metadata["rendered_at"] = local_now().isoformat()
    runtime._write_json(metadata_path, metadata)
