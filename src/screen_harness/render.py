"""FFmpeg render helpers."""

from __future__ import annotations

import re
import subprocess
import os
from dataclasses import dataclass
from pathlib import Path


# Whitelist for filter argument values we feed to FFmpeg's filtergraph parser.
# Drawbox accepts named colors (`red`, `blue`) or `0xRRGGBB[@A.AA]`. Anything
# containing the filter-grammar metachars `:`, `,`, `;`, `[`, `]`, `'`, `\` is
# rejected outright — those would let a caller break out of the argument and
# inject extra filters.
_COLOR_RE = re.compile(r"^(?:0x[0-9A-Fa-f]{6}|[A-Za-z][A-Za-z0-9]*)(?:@[01](?:\.\d+)?)?$")
_THICKNESS_VALUES = {"fill"}
_FILTER_METACHARS = re.compile(r"[:;,\[\]\\'\"]")


def _validate_color(value: str, *, field: str) -> str:
    """Accept only named colors or `0xRRGGBB[@A.AA]`. Rejects filtergraph metachars."""
    if not isinstance(value, str) or not _COLOR_RE.fullmatch(value):
        raise ValueError(
            f"{field}={value!r} is not a valid FFmpeg color "
            "(expected a name like 'red' or '0xRRGGBB[@alpha]')"
        )
    return value


def _validate_thickness(value: int | str, *, field: str) -> str:
    """Accept positive integers or the literal string 'fill'."""
    if isinstance(value, bool):
        raise ValueError(f"{field}={value!r} must be int or 'fill'")
    if isinstance(value, int) and value > 0:
        return str(value)
    if isinstance(value, str) and value in _THICKNESS_VALUES:
        return value
    raise ValueError(f"{field}={value!r} must be a positive int or 'fill'")


def _validate_filter_token(value: str, *, field: str) -> str:
    """Reject empty / metachar-bearing values that would escape an FFmpeg filter argument."""
    if not isinstance(value, str) or not value or _FILTER_METACHARS.search(value):
        raise ValueError(f"{field}={value!r} contains characters not allowed in a filtergraph argument")
    return value


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

    def __post_init__(self) -> None:
        _validate_color(self.color, field="DrawBox.color")
        _validate_thickness(self.thickness, field="DrawBox.thickness")


@dataclass(frozen=True)
class StepPanel:
    """Frosted-glass step card overlay rendered via FFmpeg filtergraph.

    The recorder crops the base video at (x, y, width, height), blurs it,
    layers a translucent tint on top, and overlays the result back at the
    same position only during `intervals`. Step text is then burned in via
    the ASS subtitle pass that runs after the panel overlay.
    """

    x: int
    y: int
    width: int
    height: int
    intervals: list[tuple[float, float]]
    blur_radius: int = 24
    tint_color: str = "0xEEEEEE@0.55"

    def __post_init__(self) -> None:
        for field, value in (("x", self.x), ("y", self.y), ("width", self.width), ("height", self.height)):
            if not isinstance(value, int) or isinstance(value, bool):
                raise ValueError(f"StepPanel.{field}={value!r} must be int")
        if self.width <= 0 or self.height <= 0:
            raise ValueError(f"StepPanel width/height must be positive, got {self.width}x{self.height}")
        if not isinstance(self.blur_radius, int) or self.blur_radius < 0:
            raise ValueError(f"StepPanel.blur_radius={self.blur_radius!r} must be a non-negative int")
        _validate_color(self.tint_color, field="StepPanel.tint_color")


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
    step_panel: StepPanel | None = None,
    ffmpeg: str | None = None,
) -> list[str]:
    """Build an FFmpeg command that burns ASS subtitles and drawbox overlays."""
    ffmpeg = ffmpeg or _default_render_ffmpeg()
    filter_graph = _build_filter_graph(ass, boxes=boxes, step_panel=step_panel)
    return [
        ffmpeg,
        "-y",
        "-i",
        str(source),
        "-vf",
        filter_graph,
        "-c:a",
        "copy",
        str(output),
    ]


def _build_filter_graph(
    ass: Path,
    *,
    boxes: list[DrawBox] | None,
    step_panel: StepPanel | None,
) -> str:
    sub_filter = f"subtitles=filename='{_filter_escape_path(Path(ass).resolve())}'"
    box_filters = [_drawbox_filter(box) for box in (boxes or [])]
    if step_panel is None or not step_panel.intervals:
        return ",".join([sub_filter, *box_filters])
    # StepPanel.__post_init__ already validated tint_color, so direct interpolation is safe here.
    enables = "+".join(
        f"between(t\\,{a:.3f}\\,{b:.3f})" for a, b in step_panel.intervals
    )
    head = (
        "split=2[base][src];"
        f"[src]crop={step_panel.width}:{step_panel.height}:{step_panel.x}:{step_panel.y},"
        f"boxblur={int(step_panel.blur_radius)}:1,"
        f"drawbox=0:0:{step_panel.width}:{step_panel.height}:{step_panel.tint_color}:t=fill[tinted];"
        f"[base][tinted]overlay={step_panel.x}:{step_panel.y}:enable='{enables}'[paneled];"
        f"[paneled]{sub_filter}"
    )
    if box_filters:
        return head + "," + ",".join(box_filters)
    return head


def build_intro_source_command(
    output: Path,
    *,
    width: int,
    height: int,
    fps: float,
    duration: float,
    background_color: str = "white",
    with_audio: bool = False,
    ffmpeg: str | None = None,
) -> list[str]:
    """Build an FFmpeg command that creates a solid-color intro source clip.

    When `with_audio=True`, a silent stereo 48 kHz AAC track of matching
    duration is added so the clip can be concatenated with audio-bearing
    main recordings without dropping the audio stream.
    """
    _validate_filter_token(background_color, field="background_color")
    ffmpeg = ffmpeg or _default_render_ffmpeg()
    cmd = [
        ffmpeg,
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c={background_color}:s={int(width)}x{int(height)}:r={float(fps)}:d={float(duration)}",
    ]
    if with_audio:
        cmd.extend([
            "-f",
            "lavfi",
            "-i",
            f"anullsrc=channel_layout=stereo:sample_rate=48000:duration={float(duration)}",
            "-c:a",
            "aac",
        ])
    cmd.extend([
        "-pix_fmt",
        "yuv420p",
        str(output),
    ])
    return cmd


def build_concat_command(
    *clips_and_output: Path,
    audio: bool = False,
    ffmpeg: str | None = None,
) -> list[str]:
    """Build an FFmpeg command that concatenates N video clips into the final.

    Call as `build_concat_command(intro, main, output)` or
    `build_concat_command(intro, main, outro, output)` — the last positional
    argument is always the output path. When `audio=True`, every input clip
    must carry an audio stream (silent counts; see `with_audio=` on
    `build_intro_source_command`).
    """
    if len(clips_and_output) < 3:
        raise ValueError("build_concat_command needs at least two input clips and one output")
    *clips, output = clips_and_output
    ffmpeg = ffmpeg or _default_render_ffmpeg()
    cmd: list[str] = [ffmpeg, "-y"]
    for clip in clips:
        cmd.extend(["-i", str(clip)])
    if audio:
        # Normalize every input's audio stream to stereo / 48 kHz / fltp before
        # the concat filter — clips coming from `anullsrc` (intro/outro) and a
        # mic-recorded main may have different layouts/sample rates, and concat
        # rejects mismatched streams. Silent intro/outro tracks stay silent
        # (anullsrc → aformat is a no-op for already-stereo-48k input; for
        # mismatched mic input it does real DSP — resample + remix — but that's
        # exactly the point).
        #
        # Pad order matters: FFmpeg's concat filter expects per-segment
        # interleaved video+audio pads ([v0][a0][v1][a1]…), NOT all-video then
        # all-audio. The latter mis-routes streams and fails at runtime.
        normalize_filters = [
            f"[{i}:a:0]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[a{i}]"
            for i in range(len(clips))
        ]
        interleaved_pads = "".join(f"[{i}:v:0][a{i}]" for i in range(len(clips)))
        graph_parts = list(normalize_filters) + [
            f"{interleaved_pads}concat=n={len(clips)}:v=1:a=1[v][a]"
        ]
        cmd.extend([
            "-filter_complex",
            ";".join(graph_parts),
            "-map",
            "[v]",
            "-map",
            "[a]",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            str(output),
        ])
    else:
        streams = "".join(f"[{i}:v:0]" for i in range(len(clips)))
        cmd.extend([
            "-filter_complex",
            f"{streams}concat=n={len(clips)}:v=1:a=0[v]",
            "-map",
            "[v]",
            "-pix_fmt",
            "yuv420p",
            str(output),
        ])
    return cmd


def render_video(
    source: Path,
    ass: Path,
    output: Path,
    *,
    boxes: list[DrawBox] | None = None,
    step_panel: StepPanel | None = None,
    ffmpeg: str | None = None,
) -> subprocess.CompletedProcess[str]:
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    cmd = build_render_command(source, ass, output, boxes=boxes, step_panel=step_panel, ffmpeg=ffmpeg)
    return subprocess.run(cmd, check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


def create_intro_source(
    output: Path,
    *,
    width: int,
    height: int,
    fps: float,
    duration: float,
    background_color: str = "white",
    with_audio: bool = False,
    ffmpeg: str | None = None,
) -> subprocess.CompletedProcess[str]:
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    cmd = build_intro_source_command(
        output,
        width=width,
        height=height,
        fps=fps,
        duration=duration,
        background_color=background_color,
        with_audio=with_audio,
        ffmpeg=ffmpeg,
    )
    return subprocess.run(cmd, check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


def concat_videos(
    *clips_and_output: Path,
    audio: bool = False,
    ffmpeg: str | None = None,
) -> subprocess.CompletedProcess[str]:
    *_, output = clips_and_output
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    cmd = build_concat_command(*clips_and_output, audio=audio, ffmpeg=ffmpeg)
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
    # Color/thickness are validated in DrawBox.__post_init__, so direct interpolation is safe.
    if box.duration is None:
        enable = "gte(t\\,{:.3f})".format(box.start)
    else:
        enable = "between(t\\,{:.3f}\\,{:.3f})".format(box.start, box.start + box.duration)
    return (
        f"drawbox=x={int(box.x)}:y={int(box.y)}:w={int(box.width)}:h={int(box.height)}:"
        f"color={box.color}:t={box.thickness}:enable='{enable}'"
    )


def _filter_escape_path(path: Path) -> str:
    """Escape a filesystem path for FFmpeg's `filename=` filter argument.

    Doubles backslashes, escapes `:` and `'` so the path can sit inside a
    quoted `filename='...'` value without breaking out of the argument.
    """
    value = str(path)
    return value.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def _ass_escape(value: str) -> str:
    """Escape user-supplied text for embedding inside an ASS dialogue line.

    Beyond the obvious `\\` and `\n` handling, this also escapes `{` and `}`
    so a malicious or accidental brace cannot terminate the surrounding
    override block (e.g. break out of `{\\an7\\pos(...)}` and inject `\\fs200`).
    """
    return (
        value.replace("\\", "\\\\")
        .replace("\n", r"\N")
        .replace("{", r"\{")
        .replace("}", r"\}")
    )


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
