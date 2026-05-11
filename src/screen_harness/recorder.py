"""FFmpeg recorder wrapper."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .screens import ScreenDevice


def build_screen_record_command(
    output: Path,
    *,
    duration: int | float | None,
    screen_index: str = "0",
    screen_device: "ScreenDevice | None" = None,
    audio_index: str | None = None,
    ffmpeg: str = "ffmpeg",
    framerate: int = 30,
    capture_cursor: bool = True,
    capture_mouse_clicks: bool = True,
    region: tuple[int, int, int, int] | None = None,
) -> list[str]:
    """Build an AVFoundation screen-recording command.

    `region`, if provided, is `(x, y, width, height)` in screen-pixel coordinates;
    the recorder crops the AVFoundation capture to that rectangle so only the
    target window (or area) is encoded. Width/height are rounded down to even
    values to satisfy H.264.

    When `screen_device` is provided it overrides `screen_index` and the device
    is validated to be a real screen (display_id != 0 sentinel).
    """
    output = Path(output)
    if screen_device is not None:
        if screen_device.display_id == 0:
            raise ValueError(
                f"refusing to record from device {screen_device.av_name!r}; "
                "expected a screen device (display_id is 0 — kCGNullDirectDisplay sentinel)"
            )
        screen_index = str(screen_device.av_index)
    av_input = f"{screen_index}:{audio_index if audio_index is not None else 'none'}"
    cmd = [
        ffmpeg,
        "-y",
        "-f",
        "avfoundation",
        "-framerate",
        str(framerate),
        "-capture_cursor",
        _ffmpeg_bool(capture_cursor),
        "-capture_mouse_clicks",
        _ffmpeg_bool(capture_mouse_clicks),
        "-i",
        av_input,
        "-r",
        str(framerate),
    ]
    if region is not None:
        x, y, w, h = (int(v) for v in region)
        if x < 0 or y < 0:
            raise ValueError(f"region x/y must be non-negative, got ({x},{y})")
        if w <= 0 or h <= 0:
            raise ValueError(f"region width/height must be positive, got {w}x{h}")
        w -= w % 2
        h -= h % 2
        if w == 0 or h == 0:
            raise ValueError(f"region width/height collapsed to zero after even-rounding from {region}")
        cmd.extend(["-vf", f"crop={w}:{h}:{x}:{y}"])
    cmd.extend(["-pix_fmt", "yuv420p"])
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
    capture_cursor: bool = True,
    capture_mouse_clicks: bool = True,
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
        capture_cursor=capture_cursor,
        capture_mouse_clicks=capture_mouse_clicks,
    )
    result = subprocess.run(cmd, check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if result.returncode == 0 and (not output.exists() or output.stat().st_size == 0):
        stdout = (result.stdout or "") + f"\nffmpeg exited 0 but did not create a non-empty output file: {output}\n"
        return subprocess.CompletedProcess(result.args, 1, stdout)
    return result


def _ffmpeg_bool(value: bool) -> str:
    return "true" if value else "false"
