"""ffmpeg / ffprobe introspection used by the recording and render paths.

Callers in other modules must invoke these via module attribute
(``probing._probe_canvas(...)``) so tests have a single patch point.
"""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

from .admin import ffmpeg_version, ffprobe_binary

logger = logging.getLogger("screen_harness")


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


def _parse_rate(value: str | None) -> float | None:
    if not value:
        return None
    if "/" in value:
        num, den = value.split("/", 1)
        denominator = float(den)
        return None if denominator == 0 else float(num) / denominator
    return float(value)
