"""macOS-gated HUD selftest: negative-space pixel check + frame-hash equivalence.

These tests require a real macOS host with PyObjC, FFmpeg avfoundation, and
a WindowServer session.  They are skipped cleanly on Linux CI.
"""

from __future__ import annotations

import hashlib
import platform
import subprocess
import sys
import time

import pytest


_on_macos = platform.system() == "Darwin"

macos_only = pytest.mark.skipif(not _on_macos, reason="macOS only")


def _pyobjc_present() -> bool:
    try:
        import Quartz  # noqa: F401
        return True
    except ImportError:
        return False


def _ffmpeg_has_avfoundation() -> bool:
    try:
        r = subprocess.run(
            ["ffmpeg", "-hide_banner", "-devices"],
            capture_output=True, text=True, timeout=10,
        )
        return "avfoundation" in r.stdout + r.stderr
    except Exception:
        return False


def _windowserver_present() -> bool:
    try:
        r = subprocess.run(["pgrep", "-x", "WindowServer"], capture_output=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return False


def _skip_integration_if_needed():
    if not _on_macos:
        pytest.skip("macOS only")
    if not _pyobjc_present():
        pytest.skip("PyObjC not installed")
    if not _ffmpeg_has_avfoundation():
        pytest.skip("FFmpeg lacks avfoundation")
    if not _windowserver_present():
        pytest.skip("headless host — no WindowServer")


def _is_hud_red(r: int, g: int, b: int) -> bool:
    """Return True if pixel matches the #FF3B30 HUD-red predicate."""
    return 230 <= r <= 255 and 40 <= g <= 80 and 30 <= b <= 70


@pytest.mark.macos
def test_hud_pixels_never_inside_crop_region(tmp_path):
    """HUD panels must not appear inside the crop region.

    Records 3 s with hud=True and region=(100,100,800,600), then scans
    5 evenly-spaced frames from the cropped video.  Asserts zero
    HUD-red pixels (#FF3B30 ± H.264 tolerance) in every frame.
    """
    _skip_integration_if_needed()

    from screen_harness import helpers

    helpers.configure(tmp_path)
    rec_dir = helpers.start_recording("hud-selftest", region=(100, 100, 800, 600), hud=True)
    time.sleep(3)
    helpers.stop_recording()

    raw = rec_dir / "raw.mp4"
    assert raw.exists(), "raw.mp4 not created"

    # Extract 5 evenly-spaced frames from the cropped video
    probe_cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=nb_frames",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(raw),
    ]
    probe_r = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=10)
    try:
        nb_frames = int(probe_r.stdout.strip())
    except ValueError:
        nb_frames = 90  # assume ~3s @ 30fps

    frame_indices = [int(nb_frames * i / 4) for i in range(5)]

    try:
        from PIL import Image
    except ImportError:
        pytest.skip("Pillow not installed")

    for fi in frame_indices:
        frame_png = tmp_path / f"frame_{fi}.png"
        extract_cmd = [
            "ffmpeg", "-y",
            "-i", str(raw),
            "-vf", f"select=eq(n\\,{fi})",
            "-vframes", "1",
            str(frame_png),
        ]
        subprocess.run(extract_cmd, capture_output=True, timeout=15)
        if not frame_png.exists():
            continue

        img = Image.open(frame_png).convert("RGB")
        px = img.load()
        w_img, h_img = img.size
        hud_red_count = sum(
            1 for y in range(h_img) for x in range(w_img)
            if _is_hud_red(px[x, y][0], px[x, y][1], px[x, y][2])
        )
        assert hud_red_count == 0, (
            f"Frame {fi}: found {hud_red_count} HUD-red pixels inside crop region. "
            "HUD coordinate bug — panels are bleeding into the recorded area."
        )


@pytest.mark.macos
def test_hud_on_vs_off_frame_hashes_match_outside_bands(tmp_path):
    """HUD-on vs HUD-off recordings produce identical cropped frame content.

    Records the same static scene twice (hud=True, hud=False) with the same
    region, then compares per-frame SHA-256 hashes for 5 sampled frames.
    Any compositing leak that changed a pixel inside the crop region would
    change the hash.
    """
    _skip_integration_if_needed()

    from screen_harness import helpers

    region = (100, 100, 800, 600)

    helpers.configure(tmp_path / "hud_on")
    (tmp_path / "hud_on").mkdir()
    rec_dir_on = helpers.start_recording("hash-test-on", region=region, hud=True)
    time.sleep(2)
    helpers.stop_recording()

    helpers.configure(tmp_path / "hud_off")
    (tmp_path / "hud_off").mkdir()
    rec_dir_off = helpers.start_recording("hash-test-off", region=region, hud=False)
    time.sleep(2)
    helpers.stop_recording()

    raw_on = rec_dir_on / "raw.mp4"
    raw_off = rec_dir_off / "raw.mp4"

    try:
        from PIL import Image
    except ImportError:
        pytest.skip("Pillow not installed")

    # Get frame counts
    def _nb_frames(path):
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=nb_frames",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, timeout=10,
        )
        try:
            return int(r.stdout.strip())
        except ValueError:
            return 60

    nb_on = _nb_frames(raw_on)
    nb_off = _nb_frames(raw_off)
    n = min(nb_on, nb_off)
    frame_indices = [int(n * i / 4) for i in range(5)]

    mismatches = 0
    for fi in frame_indices:
        def _extract(raw, tag):
            out = tmp_path / f"frame_{tag}_{fi}.png"
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(raw),
                 "-vf", f"select=eq(n\\,{fi})", "-vframes", "1", str(out)],
                capture_output=True, timeout=15,
            )
            return out

        f_on = _extract(raw_on, "on")
        f_off = _extract(raw_off, "off")
        if not f_on.exists() or not f_off.exists():
            continue

        h_on = hashlib.sha256(Image.open(f_on).tobytes()).hexdigest()
        h_off = hashlib.sha256(Image.open(f_off).tobytes()).hexdigest()
        if h_on != h_off:
            mismatches += 1

    assert mismatches == 0, (
        f"{mismatches}/5 sampled frames differ between hud=True and hud=False runs. "
        "HUD is leaking pixels into the crop region."
    )
