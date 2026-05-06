"""FFmpeg render helpers."""

from __future__ import annotations

import subprocess
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DrawBox:
    x: int
    y: int
    width: int
    height: int
    start: float = 0.0
    duration: float | None = None
    color: str = "red@0.35"
    thickness: int | str = 4


def write_spike_ass(path: Path, *, title: str, caption: str, duration: float) -> Path:
    """Write a simple ASS subtitle file for spike rendering."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    end = _ass_time(duration)
    text = f"""[Script Info]
Title: {title}
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,36,&H00FFFFFF,&H000000FF,&H7F000000,&H7F000000,0,0,0,0,100,100,0,0,1,2,0,2,40,40,42,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,{end},Default,,0,0,0,,{_ass_escape(caption)}
"""
    path.write_text(text)
    return path


def build_render_command(
    source: Path,
    ass: Path,
    output: Path,
    *,
    boxes: list[DrawBox] | None = None,
    ffmpeg: str | None = None,
) -> list[str]:
    """Build an FFmpeg command that burns ASS subtitles and drawbox overlays."""
    ffmpeg = ffmpeg or _default_render_ffmpeg()
    filters = [f"subtitles=filename='{_filter_escape_path(Path(ass).resolve())}'"]
    for box in boxes or []:
        filters.append(_drawbox_filter(box))
    return [
        ffmpeg,
        "-y",
        "-i",
        str(source),
        "-vf",
        ",".join(filters),
        "-c:a",
        "copy",
        str(output),
    ]


def build_intro_source_command(
    output: Path,
    *,
    width: int,
    height: int,
    fps: float,
    duration: float,
    ffmpeg: str | None = None,
) -> list[str]:
    """Build an FFmpeg command that creates a white intro source clip."""
    ffmpeg = ffmpeg or _default_render_ffmpeg()
    return [
        ffmpeg,
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c=white:s={int(width)}x{int(height)}:r={float(fps)}:d={float(duration)}",
        "-pix_fmt",
        "yuv420p",
        str(output),
    ]


def build_concat_command(intro: Path, main: Path, output: Path, *, ffmpeg: str | None = None) -> list[str]:
    """Build an FFmpeg command that concatenates intro and main video streams."""
    ffmpeg = ffmpeg or _default_render_ffmpeg()
    # MVP training renders are video-only after intro concat; audio passthrough needs a later compatible silent-audio plan.
    return [
        ffmpeg,
        "-y",
        "-i",
        str(intro),
        "-i",
        str(main),
        "-filter_complex",
        "[0:v:0][1:v:0]concat=n=2:v=1:a=0[v]",
        "-map",
        "[v]",
        "-pix_fmt",
        "yuv420p",
        str(output),
    ]


def render_video(
    source: Path,
    ass: Path,
    output: Path,
    *,
    boxes: list[DrawBox] | None = None,
    ffmpeg: str | None = None,
) -> subprocess.CompletedProcess[str]:
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    cmd = build_render_command(source, ass, output, boxes=boxes, ffmpeg=ffmpeg)
    return subprocess.run(cmd, check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


def create_intro_source(
    output: Path,
    *,
    width: int,
    height: int,
    fps: float,
    duration: float,
    ffmpeg: str | None = None,
) -> subprocess.CompletedProcess[str]:
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    cmd = build_intro_source_command(output, width=width, height=height, fps=fps, duration=duration, ffmpeg=ffmpeg)
    return subprocess.run(cmd, check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


def concat_videos(intro: Path, main: Path, output: Path, *, ffmpeg: str | None = None) -> subprocess.CompletedProcess[str]:
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    cmd = build_concat_command(intro, main, output, ffmpeg=ffmpeg)
    return subprocess.run(cmd, check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


def render_smoke(work_dir: Path, *, ffmpeg: str = "ffmpeg") -> subprocess.CompletedProcess[str]:
    """Generate a short source video, ASS file, and rendered output."""
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    raw = work_dir / "raw.mp4"
    ass = work_dir / "sop.ass"
    final = work_dir / "final.mp4"
    render_ffmpeg = _default_render_ffmpeg() if ffmpeg == "ffmpeg" else ffmpeg
    source_cmd = [
        ffmpeg,
        "-y",
        "-f",
        "lavfi",
        "-i",
        "testsrc2=size=640x360:rate=30",
        "-t",
        "3",
        "-pix_fmt",
        "yuv420p",
        str(raw),
    ]
    source = subprocess.run(source_cmd, check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if source.returncode != 0:
        return source
    write_spike_ass(ass, title="Screen Harness M0", caption="Milestone 0 render smoke", duration=3.0)
    return render_video(raw, ass, final, boxes=[DrawBox(x=40, y=40, width=220, height=100, start=0.5, duration=2.0)], ffmpeg=render_ffmpeg)


def _drawbox_filter(box: DrawBox) -> str:
    if box.duration is None:
        enable = "gte(t\\,{:.3f})".format(box.start)
    else:
        enable = "between(t\\,{:.3f}\\,{:.3f})".format(box.start, box.start + box.duration)
    return (
        f"drawbox=x={box.x}:y={box.y}:w={box.width}:h={box.height}:"
        f"color={box.color}:t={box.thickness}:enable='{enable}'"
    )


def _filter_escape_path(path: Path) -> str:
    value = str(path)
    return value.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def _ass_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", r"\N")


def _ass_time(seconds: float) -> str:
    hundredths = int(round(seconds * 100))
    h, rem = divmod(hundredths, 3600 * 100)
    m, rem = divmod(rem, 60 * 100)
    s, cs = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _default_render_ffmpeg() -> str:
    explicit = os.environ.get("SCREEN_HARNESS_FFMPEG")
    if explicit:
        return explicit
    full = Path("/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg")
    if full.exists():
        return str(full)
    return "ffmpeg"
