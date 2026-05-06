"""Agent-facing Screen Harness helpers."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import IO

from .admin import ffmpeg_version, ffprobe_binary
from .captions import CaptionOutputs, generate_caption_assets
from .metadata import write_text_atomic
from .project import init_project
from .redact import scan_redactions as scan_recording_redactions
from .recorder import build_screen_record_command
from .render import DrawBox, concat_videos, create_intro_source, render_video
from .sop import generate_ai_sop as generate_ai_sop_assets
from .templates import get_template
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


_STATE = RuntimeState(root=Path.cwd())
DEFAULT_HIGHLIGHT_COLOR = "blue@0.35"

__all__ = [
    "start_recording",
    "stop_recording",
    "wait",
    "wait_for_user",
    "intro",
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
    mic: str | None = None,
    intro: str | dict | None = None,
    template: str | None = None,
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
        "error": None,
    }
    _write_json(recording_dir / "metadata.json", metadata)
    log_handle = (recording_dir / "ffmpeg.log").open("w")
    cmd = build_screen_record_command(raw, duration=None, screen_index=screen or "0", audio_index=mic)
    process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=log_handle, stderr=subprocess.STDOUT)
    _STATE.recording_dir = recording_dir
    _STATE.timeline = timeline
    _STATE.started_at = time.monotonic()
    _STATE.process = process
    _STATE.log_handle = log_handle
    _STATE.is_recording = True
    return recording_dir


def stop_recording() -> Path:
    if not _STATE.is_recording or not _STATE.process or not _STATE.recording_dir:
        raise RuntimeError("no active recording")
    process = _STATE.process
    if process.stdin:
        try:
            process.stdin.write(b"q")
            process.stdin.flush()
        except BrokenPipeError:
            pass
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    if _STATE.log_handle:
        _STATE.log_handle.close()
    duration = _elapsed()
    metadata_path = _STATE.recording_dir / "metadata.json"
    metadata = json.loads(metadata_path.read_text())
    metadata["recording_stopped_at"] = datetime.now(TOKYO).isoformat()
    metadata["duration"] = round(duration, 3)
    metadata["status"] = "stopped" if process.returncode == 0 else "error"
    metadata["error"] = None if process.returncode == 0 else f"ffmpeg exited {process.returncode}"
    metadata["canvas"] = _probe_canvas(_STATE.recording_dir / "raw.mp4")
    _write_json(metadata_path, metadata)
    _STATE.is_recording = False
    return _STATE.recording_dir


def abort_active_recording() -> None:
    if not _STATE.is_recording or not _STATE.process:
        return
    try:
        _STATE.process.terminate()
        _STATE.process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        _STATE.process.kill()
        _STATE.process.wait(timeout=5)
    finally:
        if _STATE.log_handle:
            _STATE.log_handle.close()
        if _STATE.recording_dir:
            metadata_path = _STATE.recording_dir / "metadata.json"
            if metadata_path.exists():
                metadata = json.loads(metadata_path.read_text())
                metadata["recording_stopped_at"] = datetime.now(TOKYO).isoformat()
                metadata["duration"] = round(_elapsed(), 3)
                metadata["status"] = "aborted"
                metadata["error"] = "script exited before stop_recording()"
                _write_json(metadata_path, metadata)
        _STATE.is_recording = False


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


def chapter(title: str, *, t: float | None = None) -> None:
    _timeline().add_event("chapter", t=_event_time(t), title=title)


def step(title: str, *, note: str | None = None, number: int | None = None, t: float | None = None) -> None:
    _timeline().add_event("step", t=_event_time(t), title=title, note=note, number=number)


def caption(text: str, *, duration: float | None = None, t: float | None = None) -> None:
    _timeline().add_event("caption", t=_event_time(t), text=text, duration=duration)


def click(x: int, y: int, *, label: str | None = None, t: float | None = None) -> None:
    _timeline().add_event("click", t=_event_time(t), x=x, y=y, label=label)


def highlight_region(x: int, y: int, w: int, h: int, *, text: str | None = None, duration: float = 3.0, color: str | None = None) -> None:
    _timeline().add_event("highlight", t=_event_time(None), rect=[x, y, w, h], text=text, duration=duration, color=color)


def redact_region(x: int, y: int, w: int, h: int, *, reason: str | None = None, duration: float | None = None) -> None:
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
    outputs = generate_caption_assets(directory, template=template_name)
    raw = directory / "raw.mp4"
    final = directory / "final.mp4"
    timeline = Timeline.load(directory / "timeline.json")
    template_obj = get_template(template_name)
    if outputs.intro_ass and template_obj.intro_duration(timeline.data) > 0:
        canvas = _render_canvas(directory, raw)
        intro_source = directory / "intro-source.mp4"
        intro_video = directory / "intro.mp4"
        main_video = directory / "main.mp4"
        result = create_intro_source(
            intro_source,
            width=canvas["width"],
            height=canvas["height"],
            fps=canvas["fps"],
            duration=template_obj.intro_duration(timeline.data),
        )
        if result.returncode != 0:
            raise RuntimeError(result.stdout)
        result = render_video(intro_source, outputs.intro_ass, intro_video)
        if result.returncode != 0:
            raise RuntimeError(result.stdout)
        result = render_video(raw, outputs.ass, main_video, boxes=_drawboxes(timeline.data))
        if result.returncode != 0:
            raise RuntimeError(result.stdout)
        result = concat_videos(intro_video, main_video, final)
    else:
        result = render_video(raw, outputs.ass, final, boxes=_drawboxes(timeline.data))
    if result.returncode != 0:
        raise RuntimeError(result.stdout)
    _write_render_metadata(directory, template_name, final)
    return final


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


def _drawboxes(data: dict) -> list[DrawBox]:
    boxes: list[DrawBox] = []
    for event in data.get("events", []):
        if event["type"] == "highlight":
            x, y, w, h = event["rect"]
            boxes.append(
                DrawBox(
                    x=x,
                    y=y,
                    width=w,
                    height=h,
                    start=event["t"],
                    duration=event.get("duration", 3.0),
                    color=event.get("color", DEFAULT_HIGHLIGHT_COLOR),
                )
            )
        elif event["type"] == "redact":
            x, y, w, h = event["rect"]
            boxes.append(DrawBox(x=x, y=y, width=w, height=h, start=event["t"], duration=event.get("duration"), color="black@0.85", thickness="fill"))
        elif event["type"] == "click":
            boxes.append(DrawBox(x=max(0, event["x"] - 18), y=max(0, event["y"] - 18), width=36, height=36, start=event["t"], duration=1.0, color="red@0.45"))
    return boxes


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
    metadata_path = Path(directory) / "metadata.json"
    canvas = None
    if metadata_path.exists():
        try:
            canvas = json.loads(metadata_path.read_text()).get("canvas")
        except json.JSONDecodeError:
            canvas = None
    canvas = canvas or _probe_canvas(raw) or {}
    return {
        "width": int(canvas.get("width") or 1920),
        "height": int(canvas.get("height") or 1080),
        "fps": float(canvas.get("fps") or 30.0),
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
