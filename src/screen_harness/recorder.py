"""FFmpeg recorder wrapper."""

from __future__ import annotations

import subprocess
from pathlib import Path


def build_screen_record_command(
    output: Path,
    *,
    duration: int | float | None,
    screen_index: str = "0",
    audio_index: str | None = None,
    ffmpeg: str = "ffmpeg",
    framerate: int = 30,
) -> list[str]:
    """Build an AVFoundation screen-recording command."""
    output = Path(output)
    av_input = f"{screen_index}:{audio_index if audio_index is not None else 'none'}"
    cmd = [
        ffmpeg,
        "-y",
        "-f",
        "avfoundation",
        "-framerate",
        str(framerate),
        "-i",
        av_input,
        "-r",
        str(framerate),
        "-pix_fmt",
        "yuv420p",
    ]
    if duration is not None:
        cmd.extend(["-t", str(duration)])
    cmd.append(str(output))
    return cmd


def record_screen(
    output: Path,
    *,
    duration: int | float,
    screen_index: str = "0",
    audio_index: str | None = None,
    ffmpeg: str = "ffmpeg",
) -> subprocess.CompletedProcess[str]:
    """Record the main display to an output file for a fixed duration."""
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    cmd = build_screen_record_command(
        output,
        duration=duration,
        screen_index=screen_index,
        audio_index=audio_index,
        ffmpeg=ffmpeg,
    )
    result = subprocess.run(cmd, check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if result.returncode == 0 and (not output.exists() or output.stat().st_size == 0):
        stdout = (result.stdout or "") + f"\nffmpeg exited 0 but did not create a non-empty output file: {output}\n"
        return subprocess.CompletedProcess(result.args, 1, stdout)
    return result
