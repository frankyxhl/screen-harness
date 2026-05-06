"""Administrative checks for the Screen Harness spike."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AVFoundationDevices:
    video: list[dict[str, str]]
    audio: list[dict[str, str]]


_DEVICE_RE = re.compile(r"\[(?P<index>\d+)] (?P<name>.+)$")


def parse_avfoundation_devices(text: str) -> AVFoundationDevices:
    """Parse FFmpeg AVFoundation device-list output."""
    section: str | None = None
    video: list[dict[str, str]] = []
    audio: list[dict[str, str]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if "AVFoundation video devices:" in line:
            section = "video"
            continue
        if "AVFoundation audio devices:" in line:
            section = "audio"
            continue
        match = _DEVICE_RE.search(line)
        if not match or section not in {"video", "audio"}:
            continue
        item = {"index": match.group("index"), "name": match.group("name")}
        if section == "video":
            video.append(item)
        else:
            audio.append(item)
    return AVFoundationDevices(video=video, audio=audio)


def ffmpeg_version(ffmpeg: str = "ffmpeg") -> str:
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-version"],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return result.stdout.splitlines()[0] if result.stdout else ""


def ffmpeg_filters(ffmpeg: str = "ffmpeg") -> set[str]:
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-filters"],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return parse_ffmpeg_filters(result.stdout)


def parse_ffmpeg_filters(text: str) -> set[str]:
    filters: set[str] = set()
    for raw_line in text.splitlines():
        parts = raw_line.split()
        if len(parts) >= 2 and re.fullmatch(r"[TSC.]{2,4}", parts[0]):
            filters.add(parts[1])
    return filters


def bundled_full_ffmpeg() -> str | None:
    path = Path("/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg")
    return str(path) if path.exists() else None


def ffprobe_binary() -> str:
    configured = os.environ.get("SCREEN_HARNESS_FFPROBE")
    if configured:
        return configured
    configured_ffmpeg = os.environ.get("SCREEN_HARNESS_FFMPEG")
    if configured_ffmpeg:
        sibling = Path(configured_ffmpeg).with_name("ffprobe")
        if sibling.exists():
            return str(sibling)
    return shutil.which("ffprobe") or "ffprobe"


def list_avfoundation_devices(ffmpeg: str = "ffmpeg") -> tuple[AVFoundationDevices, str | None]:
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-f", "avfoundation", "-list_devices", "true", "-i", ""],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    devices = parse_avfoundation_devices(result.stdout)
    error = None if result.returncode == 0 else _last_error_line(result.stdout)
    return devices, error


def _last_error_line(text: str) -> str | None:
    for line in reversed(text.splitlines()):
        stripped = line.strip()
        if stripped:
            return stripped
    return None


def build_doctor_summary(
    *,
    ffmpeg_path: str | None,
    ffmpeg_version: str | None,
    devices: AVFoundationDevices,
    device_error: str | None = None,
    render_ffmpeg_path: str | None = None,
    render_filters_ok: bool | None = None,
) -> str:
    lines = []
    if ffmpeg_path:
        lines.append(f"ffmpeg: ok — {ffmpeg_path}")
        if ffmpeg_version:
            lines.append(f"ffmpeg version: {ffmpeg_version}")
    else:
        lines.append("ffmpeg: missing — install FFmpeg and ensure it is on PATH")
    screen_devices = [d for d in devices.video if "screen" in d["name"].lower()]
    if screen_devices:
        names = ", ".join(f'{d["index"]}:{d["name"]}' for d in screen_devices)
        lines.append(f"screen capture: ok — {names}")
    else:
        lines.append("screen capture: not detected — grant Screen Recording permission and retry")
    if devices.audio:
        names = ", ".join(f'{d["index"]}:{d["name"]}' for d in devices.audio)
        lines.append(f"microphone: ok — {names}")
    else:
        lines.append("microphone: not detected — grant Microphone permission or record without audio")
    if device_error:
        lines.append(f"device probe note: {device_error}")
    if render_ffmpeg_path:
        status = "ok" if render_filters_ok else "missing required filters"
        lines.append(f"render ffmpeg: {status} — {render_ffmpeg_path}")
    elif render_filters_ok is False:
        lines.append("render ffmpeg: missing — need FFmpeg with subtitles/ass and drawbox filters")
    return "\n".join(lines)


def doctor() -> str:
    ffmpeg_path = shutil.which("ffmpeg")
    render_ffmpeg_path = bundled_full_ffmpeg() or ffmpeg_path
    version = None
    devices = AVFoundationDevices(video=[], audio=[])
    device_error = None
    render_filters_ok = None
    if ffmpeg_path:
        try:
            version = ffmpeg_version(ffmpeg_path)
        except (OSError, subprocess.SubprocessError) as exc:
            version = f"unavailable: {exc}"
        try:
            devices, device_error = list_avfoundation_devices(ffmpeg_path)
        except OSError as exc:
            device_error = str(exc)
    if render_ffmpeg_path:
        try:
            filters = ffmpeg_filters(render_ffmpeg_path)
            render_filters_ok = bool({"subtitles", "drawbox"}.issubset(filters) or {"ass", "drawbox"}.issubset(filters))
        except (OSError, subprocess.SubprocessError):
            render_filters_ok = False
    else:
        render_filters_ok = False
    return build_doctor_summary(
        ffmpeg_path=ffmpeg_path,
        ffmpeg_version=version,
        devices=devices,
        device_error=device_error,
        render_ffmpeg_path=render_ffmpeg_path,
        render_filters_ok=render_filters_ok,
    )


def run_doctor() -> int:
    print(doctor())
    return 0
