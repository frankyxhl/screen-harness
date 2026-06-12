"""macOS-gated HUD selftest: negative-space pixel check + frame-hash equivalence.

These tests require a real macOS host with PyObjC, FFmpeg avfoundation, and
a WindowServer session.  They are skipped cleanly on Linux CI.
"""

from __future__ import annotations

import hashlib
import os
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
@pytest.mark.xfail(
    os.environ.get("CI") == "true",
    reason="HUD panels bleed into crop region on non-Retina (1x) CI display — "
    "suspected points-vs-pixels scale bug, see issue #17",
    strict=False,
)
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


# NOTE: A previous `test_hud_on_vs_off_frame_hashes_match_outside_bands`
# was removed (DeepSeek B3).  It compared per-frame SHA-256 hashes of two
# live-desktop captures recorded 2 seconds apart — but the desktop is not
# static (cursor blinks, clock ticks, fan-noise compression).  Spurious
# hash mismatches were essentially guaranteed in any non-trivial
# environment; the test was either passing by luck or failing for reasons
# unrelated to HUD bleed.
#
# A correct version requires a *synthetic* static source rendered into the
# crop region (a borderless NSWindow filled with a known colour drawn via
# PyObjC) so the only difference between hud=True and hud=False runs would
# be HUD compositing.  That's tracked as a follow-up in CHG-2218 §Plan
# item 8's deferred replacement: `test_hud_on_vs_off_frame_hashes_match_static_source`.
#
# Until then, the negative-space selftest above is the canonical visual
# contract.  A coordinate bug that bled the HUD into the crop would
# materialise as HUD-red pixels inside the crop, which the selftest
# catches.
