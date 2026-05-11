"""D2 control spike: same as d2_spike.py but with sharingType=DEFAULT (not .none).

If sharingType were the load-bearing flag, the recording should now show red.
"""
from __future__ import annotations

import shutil, subprocess, sys, threading, time
from pathlib import Path

from AppKit import (
    NSApplication, NSApp, NSPanel, NSColor, NSScreen,
    NSWindowSharingReadOnly,  # the DEFAULT
    NSScreenSaverWindowLevel,
    NSWindowCollectionBehaviorCanJoinAllSpaces,
    NSWindowCollectionBehaviorStationary,
    NSBackingStoreBuffered, NSBorderlessWindowMask,
)
from Foundation import NSMakeRect
from PyObjCTools import AppHelper

PANEL_W, PANEL_H, MARGIN = 240, 90, 24


def main():
    NSApplication.sharedApplication()
    screen = NSScreen.mainScreen()
    sframe = screen.frame()
    x = sframe.size.width - PANEL_W - MARGIN
    y = sframe.size.height - PANEL_H - MARGIN  # AppKit bottom-left
    rect = NSMakeRect(x, y, PANEL_W, PANEL_H)
    panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
        rect, NSBorderlessWindowMask, NSBackingStoreBuffered, False)
    panel.setBackgroundColor_(NSColor.colorWithCalibratedRed_green_blue_alpha_(1.0, 0.0, 0.0, 1.0))
    panel.setOpaque_(True)
    panel.setLevel_(NSScreenSaverWindowLevel)
    panel.setIgnoresMouseEvents_(True)
    panel.setSharingType_(NSWindowSharingReadOnly)  # ← DEFAULT (recordable)
    panel.setCollectionBehavior_(
        NSWindowCollectionBehaviorCanJoinAllSpaces | NSWindowCollectionBehaviorStationary)
    panel.orderFrontRegardless()

    raw = Path("agent-workspace/d2_spike_control_raw.mp4").resolve()
    if raw.exists(): raw.unlink()

    def _ff():
        time.sleep(1.0)  # extra time so panel renders before capture
        subprocess.run([
            "ffmpeg","-y","-hide_banner","-loglevel","error",
            "-f","avfoundation","-framerate","30",
            "-capture_cursor","false",
            "-i","0:none",
            "-t","3","-pix_fmt","yuv420p",
            str(raw),
        ])
        AppHelper.callAfter(lambda: NSApp.terminate_(None))

    threading.Thread(target=_ff, daemon=True).start()
    NSApp.run()
    print(f"\nControl raw saved: {raw} ({raw.stat().st_size if raw.exists() else 0} bytes)")


if __name__ == "__main__":
    sys.exit(main())
