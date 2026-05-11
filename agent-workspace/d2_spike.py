"""D2 spike: does NSWindowSharingNone hide an NSPanel from FFmpeg avfoundation?

Run from project root:
  uv run --with pyobjc python agent-workspace/d2_spike.py

Process model:
  - main thread = AppKit run loop with one red NSPanel (sharingType=.none)
  - background thread = launches FFmpeg avfoundation for 3s
  - after FFmpeg exits, sample pixels from raw and report
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import objc
from AppKit import (
    NSApplication,
    NSApp,
    NSWindow,
    NSPanel,
    NSColor,
    NSScreen,
    NSWindowSharingNone,
    NSScreenSaverWindowLevel,
    NSWindowCollectionBehaviorCanJoinAllSpaces,
    NSWindowCollectionBehaviorStationary,
    NSBackingStoreBuffered,
    NSBorderlessWindowMask,
    NSColorSpace,
)
from Foundation import NSMakeRect, NSTimer

# Region for the red panel: 200x80 at top-right of main screen
PANEL_W, PANEL_H = 240, 90
PANEL_MARGIN = 24


def find_screen_device_index() -> str:
    """Pick the AVFoundation device index whose section contains 'screen'/locale equivalents."""
    out = subprocess.run(
        ["ffmpeg", "-hide_banner", "-f", "avfoundation", "-list_devices", "true", "-i", ""],
        capture_output=True, text=True,
    ).stderr  # ffmpeg prints device list on stderr
    # Find lines after "AVFoundation video devices:" until "AVFoundation audio devices:"
    in_video = False
    candidates = []
    for line in out.splitlines():
        if "AVFoundation video devices" in line:
            in_video = True
            continue
        if "AVFoundation audio devices" in line:
            in_video = False
            continue
        if in_video and "] " in line:
            # e.g. "[AVFoundation indev @ 0x...] [1] Capture screen 0"
            try:
                idx_part = line.split("] ")[-2].split("[")[-1]
                name = line.split("] ")[-1].strip()
                candidates.append((idx_part, name))
            except Exception:
                pass
    print("AVFoundation video devices:")
    for idx, name in candidates:
        print(f"  [{idx}] {name}")
    # heuristic: pick the one whose name looks like a screen (contains digit OR is the highest index)
    screen_like = [(i, n) for i, n in candidates if any(t in n.lower() for t in ("screen", "capture", "pantalla", "écran", "屏幕", "画面"))]
    if not screen_like:
        # fallback: last one (AVFoundation lists cameras first, screens last)
        screen_like = [candidates[-1]] if candidates else []
    if not screen_like:
        raise SystemExit("No AVFoundation video devices found")
    idx, name = screen_like[0]
    print(f"\nPicked screen device: [{idx}] {name}\n")
    return idx


def make_red_panel() -> NSPanel:
    screen = NSScreen.mainScreen()
    sframe = screen.frame()
    x = sframe.size.width - PANEL_W - PANEL_MARGIN
    y = sframe.size.height - PANEL_H - PANEL_MARGIN  # AppKit bottom-left origin
    rect = NSMakeRect(x, y, PANEL_W, PANEL_H)
    panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
        rect, NSBorderlessWindowMask, NSBackingStoreBuffered, False
    )
    panel.setBackgroundColor_(NSColor.colorWithCalibratedRed_green_blue_alpha_(1.0, 0.0, 0.0, 1.0))
    panel.setOpaque_(True)
    panel.setLevel_(NSScreenSaverWindowLevel)
    panel.setIgnoresMouseEvents_(True)
    panel.setSharingType_(NSWindowSharingNone)  # ← the load-bearing flag
    panel.setCollectionBehavior_(
        NSWindowCollectionBehaviorCanJoinAllSpaces | NSWindowCollectionBehaviorStationary
    )
    panel.orderFrontRegardless()
    print(f"Red NSPanel placed at AppKit rect=({x:.0f},{y:.0f},{PANEL_W},{PANEL_H}); sharingType=NSWindowSharingNone")
    return panel


def run_ffmpeg(out_path: Path, device_index: str, duration: int = 3) -> int:
    cmd = [
        "ffmpeg", "-y", "-hide_banner",
        "-f", "avfoundation",
        "-framerate", "30",
        "-capture_cursor", "false",
        "-i", f"{device_index}:none",
        "-t", str(duration),
        "-pix_fmt", "yuv420p",
        str(out_path),
    ]
    print(f"Running: {' '.join(cmd)}")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print("FFmpeg stderr (last 30 lines):")
        for line in proc.stderr.splitlines()[-30:]:
            print(" ", line)
    return proc.returncode


def sample_red(raw_path: Path) -> dict:
    """Use ffprobe + ffmpeg to sample pixels from the top-right region and check for red dominance."""
    # Get video dims
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-of", "json", str(raw_path)],
        capture_output=True, text=True,
    )
    info = json.loads(probe.stdout)["streams"][0]
    W, H = int(info["width"]), int(info["height"])
    print(f"\nraw.mp4 dimensions: {W}x{H}")

    # Compute the crop region in PIXEL space corresponding to where the panel is.
    # AppKit panel is at top-right with margin; raw is captured in pixel space, top-left origin.
    # backing scale ~2 on Retina; estimate via screen.frame() vs raw size.
    main = NSScreen.mainScreen()
    sframe = main.frame()
    # If raw H is roughly 2 * sframe.height => Retina 2x. Use ratio.
    scale = H / sframe.size.height
    panel_px_w = int(PANEL_W * scale)
    panel_px_h = int(PANEL_H * scale)
    panel_px_x = W - panel_px_w - int(PANEL_MARGIN * scale)
    panel_px_y = int(PANEL_MARGIN * scale)
    print(f"Sampling region (top-left origin px): x={panel_px_x} y={panel_px_y} w={panel_px_w} h={panel_px_h} (scale={scale:.2f})")

    # Extract middle frame from sampled region as a raw RGB ppm
    with tempfile.TemporaryDirectory() as td:
        out_png = Path(td) / "sample.png"
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(raw_path),
            "-vf", f"crop={panel_px_w}:{panel_px_h}:{panel_px_x}:{panel_px_y},scale=20:8",
            "-frames:v", "1",
            "-ss", "1.5",
            str(out_png),
        ]
        subprocess.run(cmd, check=True)
        # Use ffmpeg to dump pixel mean
        stat_cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "info",
            "-i", str(out_png),
            "-vf", "signalstats", "-f", "null", "-",
        ]
        proc = subprocess.run(stat_cmd, capture_output=True, text=True)
        # Parse YAVG, UAVG, VAVG from output
        # Easier: use ffprobe to get per-channel average
        rgb_cmd = [
            "ffprobe", "-v", "error", "-f", "lavfi",
            "-i", f"movie={out_png},format=rgb24",
            "-show_entries", "frame=pkt_pts_time:frame_tags",
            "-of", "default=noprint_wrappers=1",
        ]
        # Simpler: use Python PIL via uv if available; else parse the signalstats output we already have.
    # Fallback: use ffmpeg to compute averages via "blockdetect"/signalstats not stable cross-version.
    # Use ImageMagick-style: ffmpeg can emit averages with the "showinfo" + crop trick — but most
    # reliable is to use PIL. Try importing.
    try:
        from PIL import Image  # type: ignore
    except ImportError:
        return {"error": "PIL not available — install pillow", "panel_rect_px": [panel_px_x, panel_px_y, panel_px_w, panel_px_h]}
    # Re-extract a small PNG for PIL
    with tempfile.TemporaryDirectory() as td:
        out_png = Path(td) / "sample.png"
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-ss", "1.5", "-i", str(raw_path),
            "-vf", f"crop={panel_px_w}:{panel_px_h}:{panel_px_x}:{panel_px_y}",
            "-frames:v", "1",
            str(out_png),
        ]
        subprocess.run(cmd, check=True)
        img = Image.open(out_png).convert("RGB")
        pixels = list(img.getdata())
        n = len(pixels)
        r_sum = sum(p[0] for p in pixels)
        g_sum = sum(p[1] for p in pixels)
        b_sum = sum(p[2] for p in pixels)
        red_pixels = sum(1 for p in pixels if p[0] > 200 and p[1] < 80 and p[2] < 80)
        return {
            "n_pixels": n,
            "avg_rgb": [r_sum / n, g_sum / n, b_sum / n],
            "red_pixel_count": red_pixels,
            "red_pixel_pct": 100 * red_pixels / n,
            "panel_rect_px": [panel_px_x, panel_px_y, panel_px_w, panel_px_h],
        }


def main():
    if shutil.which("ffmpeg") is None:
        raise SystemExit("ffmpeg not on PATH")

    NSApplication.sharedApplication()
    panel = make_red_panel()

    device_idx = find_screen_device_index()

    raw_path = Path("agent-workspace/d2_spike_raw.mp4").resolve()
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    if raw_path.exists():
        raw_path.unlink()

    rc_holder: dict = {}

    def _ff_thread():
        # small delay so AppKit has a chance to draw the panel before capture starts
        time.sleep(0.4)
        rc_holder["rc"] = run_ffmpeg(raw_path, device_idx, duration=3)
        # Stop AppKit run loop
        def _stop():
            NSApp.terminate_(None)
        # schedule on main thread
        from PyObjCTools import AppHelper
        AppHelper.callAfter(_stop)

    t = threading.Thread(target=_ff_thread, daemon=True)
    t.start()

    # Run AppKit on main thread; will exit when ff_thread terminates the app
    NSApp.run()
    t.join(timeout=5)

    print("\n=== FFmpeg done, rc =", rc_holder.get("rc"))
    if not raw_path.exists() or raw_path.stat().st_size == 0:
        print("FAIL: raw.mp4 missing or empty")
        return 2

    result = sample_red(raw_path)
    print("\n=== PIXEL ANALYSIS ===")
    print(json.dumps(result, indent=2))

    if "error" in result:
        return 3

    red_pct = result["red_pixel_pct"]
    print("\n=== VERDICT ===")
    if red_pct > 50:
        print(f"❌ sharingType=.none DID NOT WORK: {red_pct:.1f}% of panel-region pixels are red — HUD got recorded.")
        print("   → D2 must abandon the sharingType approach.")
        return 1
    elif red_pct > 5:
        print(f"⚠️  PARTIAL: {red_pct:.1f}% red — HUD partially leaked.")
        return 1
    else:
        print(f"✅ sharingType=.none WORKED: only {red_pct:.1f}% red pixels — HUD invisible to FFmpeg.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
