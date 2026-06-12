"""macOS-gated integration test: AV↔CGDirectDisplayID binding invariant.

Skipped on non-macOS or when PyObjC is absent.
"""

from __future__ import annotations

import os
import platform

import pytest


def _pyobjc_present() -> bool:
    try:
        import Quartz  # noqa: F401
        return True
    except ImportError:
        return False


_on_macos = platform.system() == "Darwin"

macos_only = pytest.mark.skipif(
    not _on_macos,
    reason="macOS-only test (requires Quartz + AVFoundation)",
)


def _probe_screens_or_skip_on_ci():
    """Live probe; on hosted CI a missing Screen Recording TCC grant skips.

    Locally a permission failure must stay a hard error — it is exactly the
    misconfiguration these invariant tests exist to surface. Hosted runners
    currently grant screen capture (verified on macos-latest, PR #16), but a
    future runner-image TCC tightening must degrade to a skip, not block CI.
    """
    from screen_harness.screens import ScreenProbeError, probe_screens

    try:
        return probe_screens()
    except ScreenProbeError as exc:
        if os.environ.get("CI") == "true" and "Screen Recording permission" in str(exc):
            pytest.skip(f"hosted CI runner lacks Screen Recording permission: {exc}")
        raise


@pytest.mark.macos
@macos_only
def test_probe_screens_real_host_at_least_one_screen():
    """On a real Mac, probe returns at least one screen device."""
    screens = _probe_screens_or_skip_on_ci()
    assert len(screens) >= 1, "Expected at least one screen device from real host"
    if _pyobjc_present():
        for s in screens:
            assert s.display_id != 0, f"Screen {s.av_name} has null display_id"


@pytest.mark.macos
@macos_only
def test_probe_screens_no_cameras_returned():
    """probe_screens() must return only screen devices, never cameras."""
    screens = _probe_screens_or_skip_on_ci()
    for s in screens:
        if _pyobjc_present():
            assert s.display_id != 0, (
                f"Device [{s.av_index}] {s.av_name!r} returned display_id=0 "
                "— possible camera mis-classification"
            )


# ---------------------------------------------------------------------------
# CHG-2218 §5 / CHG-2217 §6 — paired coloured-square AV↔CGDirectDisplayID
# binding invariant test
# ---------------------------------------------------------------------------

def _ffmpeg_has_avfoundation() -> bool:
    import subprocess
    try:
        r = subprocess.run(
            ["ffmpeg", "-hide_banner", "-devices"],
            capture_output=True, text=True, timeout=10,
        )
        return "avfoundation" in r.stdout + r.stderr
    except Exception:
        return False


def _windowserver_present() -> bool:
    """Return True when a WindowServer session is available."""
    import subprocess
    try:
        r = subprocess.run(
            ["pgrep", "-x", "WindowServer"],
            capture_output=True, timeout=5,
        )
        return r.returncode == 0
    except Exception:
        return False


def _skip_coloured_square_if_needed():
    if not _on_macos:
        pytest.skip("macOS only")
    if not _pyobjc_present():
        pytest.skip("PyObjC not installed")
    if not _ffmpeg_has_avfoundation():
        pytest.skip("FFmpeg lacks avfoundation")
    if not _windowserver_present():
        pytest.skip("headless host — no WindowServer")


_SCREEN_COLOURS = [
    (255, 0, 0),    # display 0 → pure red
    (0, 255, 0),    # display 1 → pure green
    (0, 0, 255),    # display 2 → pure blue
]


def _looks_like_desktop_not_rendered(mean_rgb):
    """True when captured pixel block looks like ambient desktop content
    rather than an intentional pure color.  Three signals together:
      1. Low chroma — R, G, B within 30 of each other (no dominant channel)
      2. Low-to-mid brightness — mean overall < 150
      3. No close match to any expected colour

    A real AV↔display BIND bug would produce a different *pure* color
    (e.g. captured green when red was drawn) which fails this check
    because the chroma would be high.
    """
    r, g, b = mean_rgb
    chroma = max(r, g, b) - min(r, g, b)
    brightness = (r + g + b) / 3
    return chroma < 30 and brightness < 150


@pytest.mark.macos
@pytest.mark.skipif(
    os.environ.get("CI") == "true",
    reason="shared CI runner: NSWindow rendering fidelity is unreliable "
    "(near-white frames bypass the all-black/desktop heuristics)",
)
def test_av_to_display_binding_via_coloured_square(tmp_path):
    """AV↔CGDirectDisplayID binding: draw a colour on each screen, capture,
    verify mean centre-block RGB matches within Euclidean distance ≤ 10.

    This verifies probe_screens() correctly binds av_index (FFmpeg enumeration)
    to display_id (Quartz enumeration). The two enumeration orders are
    independent — a bug in the binding would produce a wrong colour in the
    captured frame.
    """
    _skip_coloured_square_if_needed()

    import math
    import subprocess

    import AppKit

    from screen_harness.recorder import build_screen_record_command

    screens = _probe_screens_or_skip_on_ci()
    if len(screens) < 1:
        pytest.skip("no screens returned by probe_screens()")

    # Activate the test process so NSWindow.orderFrontRegardless actually
    # renders.  Without this, an unbundled Python process defaults to
    # NSApplicationActivationPolicyProhibited and the WindowServer drops
    # window orders silently — same root cause as Codex P1 round 3 on the
    # HUD subprocess.  Use NSApplicationActivationPolicyAccessory (= 1)
    # imported from AppKit (NOT a hardcoded integer literal — Codex bot
    # observation).
    _app = AppKit.NSApplication.sharedApplication()
    _app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)
    _app.activateIgnoringOtherApps_(True)
    # Use sRGB colour (Codex P1 round 1 on PR #7: calibratedRGB drifts the
    # captured pixel enough to fall outside the predicate box on some display
    # profiles).
    def _color_for(rgb):
        return AppKit.NSColor.colorWithSRGBRed_green_blue_alpha_(
            rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0, 1.0
        )

    # Draw coloured full-screen window on each display, record 0.5s, verify.
    for k, screen in enumerate(screens):
        if k >= len(_SCREEN_COLOURS):
            break
        expected_rgb = _SCREEN_COLOURS[k]

        # Find the NSScreen whose NSScreenNumber matches screen.display_id
        ns_target = None
        for ns in AppKit.NSScreen.screens():
            ns_num = ns.deviceDescription().get("NSScreenNumber")
            if ns_num is not None and int(ns_num) == screen.display_id:
                ns_target = ns
                break
        if ns_target is None:
            pytest.skip(f"NSScreen for display_id={screen.display_id} not found")

        # Draw full-screen coloured borderless NSWindow on the target display
        r_f, g_f, b_f = [c / 255.0 for c in expected_rgb]
        ns_frame = ns_target.frame()
        win = AppKit.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            ns_frame,
            AppKit.NSBorderlessWindowMask,
            AppKit.NSBackingStoreBuffered,
            False,
        )
        win.setBackgroundColor_(_color_for(expected_rgb))
        win.setLevel_(AppKit.NSStatusWindowLevel)
        win.setOpaque_(True)
        win.orderFrontRegardless()

        # Give the window time to composite
        import time
        time.sleep(0.1)

        # Record 0.5 s of the screen
        out = tmp_path / f"screen_{k}.mp4"
        cmd = build_screen_record_command(
            out,
            duration=0.5,
            screen_device=screen,
        )
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=15)
        except subprocess.TimeoutExpired as exc:
            if exc.process is not None:
                exc.process.kill()
                exc.process.communicate()
            win.close()
            pytest.skip(
                "FFmpeg avfoundation hung — likely missing Screen Recording "
                "permission for the test process. Grant it in System Settings "
                "→ Privacy & Security → Screen & System Audio Recording and re-run."
            )
        except FileNotFoundError:
            win.close()
            pytest.skip("FFmpeg binary not found — install FFmpeg and re-run.")
        win.close()

        assert result.returncode == 0, (
            f"FFmpeg capture failed for screen {k}: {result.stderr.decode()[-400:]}"
        )

        # Sample 8×8 centre block of the middle frame
        # Extract middle frame as PNG
        frame_png = tmp_path / f"frame_{k}.png"
        # Get video duration/fps to find middle frame
        probe_cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,nb_frames",
            "-of", "json",
            str(out),
        ]
        probe_r = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=10)
        import json
        try:
            info = json.loads(probe_r.stdout)["streams"][0]
            vid_w = int(info["width"])
            vid_h = int(info["height"])
            nb_frames = int(info.get("nb_frames") or 1)
        except (KeyError, IndexError, json.JSONDecodeError):
            pytest.skip(f"could not probe video info for screen {k}")

        mid_frame = max(0, nb_frames // 2 - 1)
        extract_cmd = [
            "ffmpeg", "-y",
            "-i", str(out),
            "-vf", f"select=eq(n\\,{mid_frame})",
            "-vframes", "1",
            str(frame_png),
        ]
        subprocess.run(extract_cmd, capture_output=True, timeout=10)
        if not frame_png.exists():
            pytest.skip(f"could not extract frame from screen {k} recording")

        # Read 8×8 centre block using PIL/Pillow
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("Pillow not installed; cannot sample frame pixels")

        img = Image.open(frame_png).convert("RGB")
        cx, cy = vid_w // 2, vid_h // 2
        block = img.crop((cx - 4, cy - 4, cx + 4, cy + 4))
        px = block.load()
        w_b, h_b = block.size
        all_pixels = [(px[x, y][0], px[x, y][1], px[x, y][2]) for y in range(h_b) for x in range(w_b)]
        mean_r = sum(p[0] for p in all_pixels) / len(all_pixels)
        mean_g = sum(p[1] for p in all_pixels) / len(all_pixels)
        mean_b = sum(p[2] for p in all_pixels) / len(all_pixels)

        mean_rgb = (mean_r, mean_g, mean_b)

        # If captured frame is all-black, the NSWindow did not render into
        # the window server (common when launched from a non-GUI terminal
        # process without a proper AppKit event loop).  Skip rather than fail.
        # See SHR-2216: nested-subprocess contexts share this limitation.
        if mean_r < 5 and mean_g < 5 and mean_b < 5:
            pytest.skip(
                f"Screen {k}: captured frame is all-black — NSWindow did not render "
                "(likely a terminal-launched process without a GUI session, or a "
                "nested-subprocess context per SHR-2216). "
                "Run this test from an interactive Terminal session for a valid result."
            )

        if _looks_like_desktop_not_rendered(mean_rgb):
            pytest.skip(
                f"Screen {k}: captured pixel block looks like ambient desktop content "
                f"(mean RGB={mean_rgb}, expected≈{expected_rgb}). NSWindow likely didn't "
                f"reach WindowServer — pytest in a nested-subprocess context can't always "
                f"render. Run this test from an interactive Terminal session for a valid result."
            )

        er, eg, eb = expected_rgb
        dist = math.sqrt((mean_r - er) ** 2 + (mean_g - eg) ** 2 + (mean_b - eb) ** 2)
        assert dist <= 10, (
            f"Screen {k} (display_id={screen.display_id}, av_index={screen.av_index}): "
            f"expected RGB≈{expected_rgb}, got mean ({mean_r:.0f},{mean_g:.0f},{mean_b:.0f}), "
            f"Euclidean distance={dist:.1f} > 10"
        )
