"""D2 spike v2: fix AppKit activation so the NSPanel actually shows.

Runs TWO trials in one process:
  Trial A: sharingType = NSWindowSharingNone  -> raw_a.mp4
  Trial B: sharingType = NSWindowSharingReadOnly (default) -> raw_b.mp4

Decision logic:
  - If A has 0 red AND B has lots of red -> sharingType WORKS for FFmpeg avfoundation.
  - If both have lots of red -> sharingType ignored, need different architecture.
  - If both 0 red -> panel still not rendering; check Screen Recording permission.
"""
from __future__ import annotations

import json, shutil, subprocess, sys, threading, time, tempfile
from pathlib import Path

from AppKit import (
    NSApplication, NSApp, NSPanel, NSColor, NSScreen, NSView, NSBezierPath,
    NSWindowSharingNone, NSWindowSharingReadOnly,
    NSScreenSaverWindowLevel, NSStatusWindowLevel, NSFloatingWindowLevel,
    NSWindowCollectionBehaviorCanJoinAllSpaces,
    NSWindowCollectionBehaviorStationary, NSWindowCollectionBehaviorFullScreenAuxiliary,
    NSBackingStoreBuffered, NSBorderlessWindowMask,
    NSApplicationActivationPolicyAccessory,
)
from Foundation import NSMakeRect, NSObject
from PyObjCTools import AppHelper

PANEL_W, PANEL_H, MARGIN = 240, 90, 24
PIXEL_RECT = (1656, 24, 240, 90)  # top-left origin in capture pixels


def make_panel(sharing_type: int) -> object:
    screen = NSScreen.mainScreen()
    sframe = screen.frame()
    x = sframe.size.width - PANEL_W - MARGIN
    y = sframe.size.height - PANEL_H - MARGIN  # AppKit bottom-left origin
    rect = NSMakeRect(x, y, PANEL_W, PANEL_H)
    panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
        rect, NSBorderlessWindowMask, NSBackingStoreBuffered, False)
    panel.setBackgroundColor_(NSColor.colorWithCalibratedRed_green_blue_alpha_(1.0, 0.0, 0.0, 1.0))
    panel.setOpaque_(True)
    panel.setHasShadow_(False)
    panel.setLevel_(NSScreenSaverWindowLevel)
    panel.setIgnoresMouseEvents_(True)
    panel.setSharingType_(sharing_type)
    panel.setCollectionBehavior_(
        NSWindowCollectionBehaviorCanJoinAllSpaces
        | NSWindowCollectionBehaviorStationary
        | NSWindowCollectionBehaviorFullScreenAuxiliary
    )
    return panel


def run_capture(out: Path):
    if out.exists(): out.unlink()
    cmd = [
        "ffmpeg","-y","-hide_banner","-loglevel","error",
        "-f","avfoundation","-framerate","30",
        "-capture_cursor","false",
        "-i","0:none",
        "-t","3","-pix_fmt","yuv420p",
        str(out),
    ]
    subprocess.run(cmd, check=False)


def analyze(raw: Path, label: str) -> dict:
    from PIL import Image
    px, py, pw, ph = PIXEL_RECT
    with tempfile.TemporaryDirectory() as td:
        crop = Path(td)/"c.png"
        full = Path(td)/"f.png"
        subprocess.run(["ffmpeg","-y","-hide_banner","-loglevel","error",
                        "-ss","1.5","-i",str(raw),
                        "-vf",f"crop={pw}:{ph}:{px}:{py}","-frames:v","1",str(crop)], check=True)
        subprocess.run(["ffmpeg","-y","-hide_banner","-loglevel","error",
                        "-ss","1.5","-i",str(raw),"-frames:v","1",str(full)], check=True)
        img = Image.open(crop).convert("RGB")
        pix = list(img.getdata())
        n = len(pix)
        avg = [sum(p[i] for p in pix)/n for i in range(3)]
        red = sum(1 for p in pix if p[0]>200 and p[1]<80 and p[2]<80)
        # Also save for visual inspection
        save_path = Path("agent-workspace") / f"d2_v2_{label}_panel.png"
        Image.open(crop).save(save_path)
        full_save = Path("agent-workspace") / f"d2_v2_{label}_full.png"
        Image.open(full).save(full_save)
    return {"label": label, "avg_rgb": avg, "red_count": red, "n": n, "red_pct": 100*red/n,
            "crop_saved": str(save_path), "full_saved": str(full_save)}


def main():
    NSApplication.sharedApplication()
    NSApp.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    NSApp.activateIgnoringOtherApps_(True)

    results = {}

    def _ff_thread():
        # Trial A: sharingType=.none
        time.sleep(0.8)  # ensure panel rendered
        run_capture(Path("agent-workspace/d2_v2_a_raw.mp4").resolve())
        AppHelper.callAfter(lambda: _switch_to_b())

    def _switch_to_b():
        # close panel A, open panel B
        for w in list(NSApp.windows()):
            w.close()
        panel_b = make_panel(NSWindowSharingReadOnly)
        panel_b.orderFrontRegardless()
        threading.Thread(target=_run_b, daemon=True).start()

    def _run_b():
        time.sleep(1.0)
        run_capture(Path("agent-workspace/d2_v2_b_raw.mp4").resolve())
        AppHelper.callAfter(lambda: NSApp.terminate_(None))

    # Start with panel A (sharingType=.none)
    panel_a = make_panel(NSWindowSharingNone)
    panel_a.orderFrontRegardless()

    threading.Thread(target=_ff_thread, daemon=True).start()
    NSApp.run()

    print("\n=== ANALYZE ===")
    a = analyze(Path("agent-workspace/d2_v2_a_raw.mp4"), "a_sharingNone")
    b = analyze(Path("agent-workspace/d2_v2_b_raw.mp4"), "b_sharingReadOnly")
    print(json.dumps(a, indent=2))
    print(json.dumps(b, indent=2))
    print()
    print("=== VERDICT ===")
    a_red = a["red_pct"]
    b_red = b["red_pct"]
    if a_red < 5 and b_red > 50:
        print(f"✅ sharingType=.none WORKS: A={a_red:.1f}% red, B={b_red:.1f}% red.")
        print("   => D2 PRP original architecture is VALID on this host (FFmpeg 8 + macOS).")
    elif a_red > 50 and b_red > 50:
        print(f"❌ sharingType IGNORED: A={a_red:.1f}% red, B={b_red:.1f}% red.")
        print("   => D2 must re-architect: HUD outside region OR switch backend.")
    elif a_red < 5 and b_red < 5:
        print(f"⚠️  PANEL NOT RENDERING: A={a_red:.1f}%, B={b_red:.1f}%. Cannot conclude.")
        print(f"   Inspect: {a['full_saved']} and {b['full_saved']}")
    else:
        print(f"⚠️  AMBIGUOUS: A={a_red:.1f}%, B={b_red:.1f}%. Manual inspection needed.")


if __name__ == "__main__":
    sys.exit(main())
