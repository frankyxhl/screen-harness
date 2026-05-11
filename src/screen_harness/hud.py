"""Recording HUD overlay for screen-harness.

This module provides:
  - Pure-function geometry helpers (importable without AppKit).
  - HUDState state machine and JSON protocol parser.
  - AppKit panel factories (lazy-imported; only used by run_hud_subprocess).
  - Entry point: ``python -m screen_harness.hud``

Architecture
------------
The HUD runs as a child subprocess of the recording parent.  The parent sends
JSON commands over the child's stdin:

    {"cmd": "start", "screen": {...}, "region": [rx, ry, rw, rh],
     "started_at": <monotonic seconds>}
    {"cmd": "stop"}
    {"cmd": "status"}

The child responds to "status" with {"status": "running"|"idle"} on stdout.

On stdin EOF (parent died or closed the pipe) the child shuts down within
200 ms via PyObjCTools.AppHelper.callAfter so the AppKit main-thread is not
touched from a background thread.

The REC pill fill colour is #FF3B30 (Apple system red, RGB 255 59 48).
Frame stroke width is 4 AppKit points.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Literal, NamedTuple

from .screens import ScreenDevice

logger = logging.getLogger("screen_harness")

# ---------------------------------------------------------------------------
# Public error types
# ---------------------------------------------------------------------------

class RegionOutOfBoundsError(ValueError):
    """Raised when a recording region extends past the picked screen's bounds."""


# ---------------------------------------------------------------------------
# Geometry helpers (pure Python, no AppKit)
# ---------------------------------------------------------------------------

def transform_region_to_appkit(
    region: tuple[int, int, int, int],
    screen: ScreenDevice,
) -> tuple[float, float, float, float]:
    """Convert a picked-screen pixel region to AppKit point coordinates.

    *region* is ``(rx, ry, rw, rh)`` in picked-screen-local pixel coordinates
    with a **top-left origin** (same convention as the ffmpeg ``crop=W:H:X:Y``
    filter).

    Returns ``(appkit_x, appkit_y, appkit_w, appkit_h)`` in the global AppKit
    coordinate space with a **bottom-left origin**.

    Conversion:
        appkit_x = screen.bounds.x + region_x / backing_scale
        appkit_y = screen.bounds.y + (screen_h_pts - (region_y + region_h) / backing_scale)
        appkit_w = region_w / backing_scale
        appkit_h = region_h / backing_scale

    where ``screen_h_pts = screen.bounds[3] / backing_scale``.
    """
    rx, ry, rw, rh = region
    bx, by, _bw, bh = screen.bounds
    s = screen.backing_scale

    screen_h_pts = bh / s
    appkit_x = bx + rx / s
    appkit_y = by + (screen_h_pts - (ry + rh) / s)
    appkit_w = rw / s
    appkit_h = rh / s
    return (appkit_x, appkit_y, appkit_w, appkit_h)


def compute_frame_stroke_rects(
    crop_rect: tuple[float, float, float, float],
    *,
    offset_pts: int = 4,
) -> tuple[
    tuple[float, float, float, float],
    tuple[float, float, float, float],
    tuple[float, float, float, float],
    tuple[float, float, float, float],
]:
    """Return four thin rect strips that form a frame around *crop_rect*.

    *crop_rect* is ``(x, y, w, h)`` in AppKit points (bottom-left origin).
    *offset_pts* is the stroke width in AppKit points (default 4).

    Returns ``(top, bottom, left, right)`` where each is
    ``(x, y, w, h)`` in AppKit points.  The strips are placed
    *outside* (adjacent to) the crop rect so they never overlap
    the recorded pixels.

    Layout (AppKit bottom-left origin):

        top    strip: x-offset..x+w+offset, y+h..y+h+offset
        bottom strip: x-offset..x+w+offset, y-offset..y
        left   strip: x-offset..x,          y-offset..y+h+offset
        right  strip: x+w..x+w+offset,      y-offset..y+h+offset
    """
    x, y, w, h = crop_rect
    o = offset_pts

    top    = (x - o, y + h,     w + 2 * o, o)
    bottom = (x - o, y - o,     w + 2 * o, o)
    left   = (x - o, y - o,     o,         h + 2 * o)
    right  = (x + w, y - o,     o,         h + 2 * o)

    return top, bottom, left, right


def format_rec_time(elapsed_seconds: int) -> str:
    """Format *elapsed_seconds* as ``HH:MM:SS``."""
    h = elapsed_seconds // 3600
    m = (elapsed_seconds % 3600) // 60
    s = elapsed_seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def pill_placement(
    anchor: str,
    crop_rect: tuple[float, float, float, float],
    *,
    pill_w: float = 160.0,
    pill_h: float = 36.0,
    margin: float = 12.0,
) -> tuple[float, float]:
    """Return ``(px, py)`` AppKit-coords for the pill given an *anchor*.

    Anchors fall into two families:

    * **Side placements** (pill sits to the left/right of the crop):
      ``bottom-right``, ``top-right``, ``bottom-left``, ``top-left``.
    * **Stacked placements** (pill sits above/below the crop) — used when
      the crop occupies the full width or full height and no side
      placement fits (Codex bot finding P2):
      ``above-right``, ``above-left``, ``below-right``, ``below-left``.

    Plus ``edge:top|bottom|left|right`` as a last-resort centered placement
    on the named screen edge — only reached when no other position fits.
    """
    cx, cy, cw, ch = crop_rect
    table = {
        "bottom-right": (cx + cw + margin, cy - pill_h - margin),
        "top-right":    (cx + cw + margin, cy + ch + margin),
        "bottom-left":  (cx - pill_w - margin, cy - pill_h - margin),
        "top-left":     (cx - pill_w - margin, cy + ch + margin),
        "above-right":  (cx + cw - pill_w,    cy + ch + margin),
        "above-left":   (cx,                  cy + ch + margin),
        "below-right":  (cx + cw - pill_w,    cy - pill_h - margin),
        "below-left":   (cx,                  cy - pill_h - margin),
    }
    if anchor in table:
        return table[anchor]
    raise ValueError(f"Unknown anchor {anchor!r} (edge: anchors are placed by caller)")


def pick_rec_pill_anchor(
    crop_rect: tuple[int | float, int | float, int | float, int | float],
    screen_rect: tuple[int | float, int | float, int | float, int | float],
    *,
    pill_w: float = 160.0,
    pill_h: float = 36.0,
    margin: float = 12.0,
) -> str:
    """Choose where to position the REC pill outside *crop_rect*.

    Eight candidate placements are tried in priority order; the first
    placement whose pill rect — including a *margin* gap from the crop
    edge — fits **entirely** inside *screen_rect* wins.  This addresses
    Codex bot finding P2: a crop of (0,0,1900,1000) on a 1920×1080
    screen leaves only 20pt to the right, which cannot fit a 160×36
    pill at the bottom-right corner anchor.

    Priority:
      1. Side placements (pill laterally adjacent to crop):
         ``bottom-right`` > ``top-right`` > ``bottom-left`` > ``top-left``
      2. Stacked placements (pill above/below crop):
         ``above-right`` > ``below-right`` > ``above-left`` > ``below-left``
      3. ``edge:<side>`` fallback for the no-fit case (crop covers the
         full screen).

    *crop_rect* and *screen_rect* are both ``(x, y, w, h)`` in the same
    coordinate system (AppKit points).
    """
    cx, cy, cw, ch = crop_rect
    sx, sy, sw, sh = screen_rect

    def _fits(px: float, py: float) -> bool:
        return (
            px >= sx
            and py >= sy
            and px + pill_w <= sx + sw
            and py + pill_h <= sy + sh
        )

    priority = [
        "bottom-right", "top-right", "bottom-left", "top-left",
        "above-right", "below-right", "above-left", "below-left",
    ]
    for anchor in priority:
        px, py = pill_placement(anchor, crop_rect, pill_w=pill_w, pill_h=pill_h, margin=margin)
        if _fits(px, py):
            return anchor

    # All corners blocked — fall back to edge closest to crop centre
    crop_cx = cx + cw / 2
    crop_cy = cy + ch / 2
    screen_cx = sx + sw / 2
    screen_cy = sy + sh / 2

    # Distances from crop centre to each screen edge
    dist_right  = abs((sx + sw) - crop_cx)
    dist_left   = abs(cx - sx)
    dist_top    = abs((sy + sh) - crop_cy)
    dist_bottom = abs(cy - sy)

    edge_distances = {
        "right":  dist_right,
        "left":   dist_left,
        "top":    dist_top,
        "bottom": dist_bottom,
    }
    closest = min(edge_distances, key=edge_distances.__getitem__)
    return f"edge:{closest}"


def _rect_contains_point(
    rect: tuple[int | float, int | float, int | float, int | float],
    px: int | float,
    py: int | float,
) -> bool:
    """Return True if (px, py) is within *rect* (inclusive of all edges)."""
    rx, ry, rw, rh = rect
    return rx <= px <= rx + rw and ry <= py <= ry + rh


# ---------------------------------------------------------------------------
# Region validation
# ---------------------------------------------------------------------------

def validate_region_for_screen(
    region: tuple[int, int, int, int],
    screen: ScreenDevice,
) -> None:
    """Raise RegionOutOfBoundsError if *region* extends past *screen* bounds.

    *region* is ``(rx, ry, rw, rh)`` in picked-screen-local pixel coordinates.
    *screen.bounds* is ``(bx, by, bw, bh)`` in global pixel coords; ``bw`` and
    ``bh`` are the screen's pixel dimensions.
    """
    rx, ry, rw, rh = region
    _bx, _by, bw, bh = screen.bounds

    if rx + rw > bw:
        raise RegionOutOfBoundsError(
            f"Region x+w ({rx}+{rw}={rx + rw}) exceeds screen width {bw}. "
            f"Run `screen-harness probe-screens` to check display dimensions."
        )
    if ry + rh > bh:
        raise RegionOutOfBoundsError(
            f"Region y+h ({ry}+{rh}={ry + rh}) exceeds screen height {bh}. "
            f"Run `screen-harness probe-screens` to check display dimensions."
        )


# ---------------------------------------------------------------------------
# JSON protocol
# ---------------------------------------------------------------------------

_VALID_CMDS = frozenset({"start", "stop", "status"})


def parse_command(line: str) -> dict:
    """Parse one JSON command line from the parent process.

    Raises ValueError on malformed input, non-object JSON, missing ``cmd``
    field, or unknown command.
    """
    if not line.strip():
        raise ValueError("empty command line")
    try:
        data = json.loads(line)
    except json.JSONDecodeError as exc:
        raise ValueError(f"malformed JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object, got {type(data).__name__}")
    cmd = data.get("cmd")
    if cmd is None:
        raise ValueError("missing 'cmd' field")
    if cmd not in _VALID_CMDS:
        raise ValueError(f"unknown command: {cmd!r} (valid: {sorted(_VALID_CMDS)})")
    return data


# ---------------------------------------------------------------------------
# HUD state machine
# ---------------------------------------------------------------------------

class HUDState:
    """Minimal state machine for the HUD subprocess command loop.

    States: idle → running → stopped
    """

    def __init__(self) -> None:
        self.state: str = "idle"
        self.region: list | None = None
        self.screen: dict | None = None
        self.started_at: float | None = None

    def handle(self, cmd: dict) -> None:
        verb = cmd["cmd"]
        if verb == "start":
            self.region = cmd.get("region")
            self.screen = cmd.get("screen")
            self.started_at = cmd.get("started_at")
            self.state = "running"
        elif verb == "stop":
            if self.state != "idle":
                self.state = "stopped"
        elif verb == "status":
            pass  # status query — no state change; response handled by caller


# ---------------------------------------------------------------------------
# AppKit helpers (lazy import — only used inside run_hud_subprocess)
# ---------------------------------------------------------------------------

def _import_appkit_deps():
    """Import all AppKit/PyObjC symbols needed by the HUD panels.

    Kept in a single lazy helper so unit tests never trigger Cocoa init.
    """
    import AppKit  # noqa: F401
    from AppKit import (
        NSApplication,
        NSBackingStoreBuffered,
        NSBorderlessWindowMask,
        NSColor,
        NSFont,
        NSMakeRect,
        NSPanel,
        NSStatusWindowLevel,
        NSTextField,
        NSTimer,
        NSWindowCollectionBehaviorCanJoinAllSpaces,
        NSWindowCollectionBehaviorFullScreenAuxiliary,
        NSWindowCollectionBehaviorStationary,
    )
    from PyObjCTools import AppHelper
    import objc

    return {
        "NSApplication": NSApplication,
        "NSBackingStoreBuffered": NSBackingStoreBuffered,
        "NSBorderlessWindowMask": NSBorderlessWindowMask,
        "NSColor": NSColor,
        "NSFont": NSFont,
        "NSMakeRect": NSMakeRect,
        "NSPanel": NSPanel,
        "NSStatusWindowLevel": NSStatusWindowLevel,
        "NSTextField": NSTextField,
        "NSTimer": NSTimer,
        "NSWindowCollectionBehaviorCanJoinAllSpaces": NSWindowCollectionBehaviorCanJoinAllSpaces,
        "NSWindowCollectionBehaviorFullScreenAuxiliary": NSWindowCollectionBehaviorFullScreenAuxiliary,
        "NSWindowCollectionBehaviorStationary": NSWindowCollectionBehaviorStationary,
        "AppHelper": AppHelper,
        "objc": objc,
    }


def _make_panel(
    frame,  # NSRect
    *,
    ak: dict,
    color_rgb: tuple[float, float, float] = (1.0, 59 / 255, 48 / 255),
) -> object:
    """Create a borderless, opaque, click-through NSPanel at *frame*."""
    NSPanel = ak["NSPanel"]
    NSBorderlessWindowMask = ak["NSBorderlessWindowMask"]
    NSBackingStoreBuffered = ak["NSBackingStoreBuffered"]
    NSColor = ak["NSColor"]
    NSStatusWindowLevel = ak["NSStatusWindowLevel"]
    NSWindowCollectionBehaviorCanJoinAllSpaces = ak["NSWindowCollectionBehaviorCanJoinAllSpaces"]
    NSWindowCollectionBehaviorStationary = ak["NSWindowCollectionBehaviorStationary"]
    NSWindowCollectionBehaviorFullScreenAuxiliary = ak["NSWindowCollectionBehaviorFullScreenAuxiliary"]

    panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
        frame,
        NSBorderlessWindowMask,
        NSBackingStoreBuffered,
        False,
    )
    panel.setLevel_(NSStatusWindowLevel)
    panel.setIgnoresMouseEvents_(True)
    panel.setOpaque_(True)
    r, g, b = color_rgb
    # NOTE: Apple's #FF3B30 is defined in sRGB.  `colorWithCalibratedRed_…_`
    # uses the legacy generic-RGB / gamma-1.8 space and drifts the captured
    # pixel value enough to fall outside the selftest predicate's tight
    # box on some display profiles.  Use sRGB explicitly.  (DeepSeek B1.)
    panel.setBackgroundColor_(NSColor.colorWithSRGBRed_green_blue_alpha_(r, g, b, 1.0))
    behavior = (
        NSWindowCollectionBehaviorCanJoinAllSpaces
        | NSWindowCollectionBehaviorStationary
        | NSWindowCollectionBehaviorFullScreenAuxiliary
    )
    panel.setCollectionBehavior_(behavior)
    panel.setReleasedWhenClosed_(False)
    return panel


# HUD red: #FF3B30 as calibrated sRGB floats
_HUD_RED_RGB = (255 / 255, 59 / 255, 48 / 255)

# Pill dimensions in AppKit points
_PILL_WIDTH = 160.0
_PILL_HEIGHT = 36.0
_PILL_MARGIN = 12.0  # gap from crop rect edge


def _make_rec_pill_panel(
    crop_appkit: tuple[float, float, float, float],
    screen_appkit: tuple[float, float, float, float],
    *,
    ak: dict,
) -> object:
    """Create and position the REC pill panel."""
    NSMakeRect = ak["NSMakeRect"]
    NSTextField = ak["NSTextField"]
    NSColor = ak["NSColor"]
    NSFont = ak["NSFont"]

    anchor = pick_rec_pill_anchor(
        crop_appkit, screen_appkit,
        pill_w=_PILL_WIDTH, pill_h=_PILL_HEIGHT, margin=_PILL_MARGIN,
    )

    sx, sy, sw, sh = screen_appkit

    if anchor.startswith("edge:"):
        # No 4-corner / 4-stack placement fits — crop covers the whole
        # screen.  Place the pill at the screen edge named by the
        # fallback; the pill will visually overlap the crop, but recording
        # is already full-screen so the user is informed via the warning
        # in helpers.start_recording.
        side = anchor.split(":", 1)[1]
        if side == "right":
            px = sx + sw - _PILL_WIDTH - _PILL_MARGIN
            py = sy + (sh - _PILL_HEIGHT) / 2
        elif side == "left":
            px = sx + _PILL_MARGIN
            py = sy + (sh - _PILL_HEIGHT) / 2
        elif side == "top":
            px = sx + (sw - _PILL_WIDTH) / 2
            py = sy + sh - _PILL_HEIGHT - _PILL_MARGIN
        else:  # bottom
            px = sx + (sw - _PILL_WIDTH) / 2
            py = sy + _PILL_MARGIN
    else:
        px, py = pill_placement(
            anchor, crop_appkit,
            pill_w=_PILL_WIDTH, pill_h=_PILL_HEIGHT, margin=_PILL_MARGIN,
        )

    frame = NSMakeRect(px, py, _PILL_WIDTH, _PILL_HEIGHT)
    panel = _make_panel(frame, ak=ak, color_rgb=_HUD_RED_RGB)

    label = NSTextField.alloc().initWithFrame_(
        NSMakeRect(8, 6, _PILL_WIDTH - 16, _PILL_HEIGHT - 12)
    )
    label.setStringValue_("● REC 00:00:00")
    label.setTextColor_(NSColor.whiteColor())
    label.setFont_(NSFont.fontWithName_size_("SF Mono", 14) or NSFont.monospacedSystemFontOfSize_weight_(14, 0))
    label.setBezeled_(False)
    label.setDrawsBackground_(False)
    label.setEditable_(False)
    label.setSelectable_(False)
    panel.contentView().addSubview_(label)

    return panel, label


def _make_frame_panels(
    crop_appkit: tuple[float, float, float, float],
    *,
    ak: dict,
) -> list:
    """Create four thin NSPanels forming a 4-pt frame outside *crop_appkit*."""
    NSMakeRect = ak["NSMakeRect"]

    rects = compute_frame_stroke_rects(crop_appkit, offset_pts=4)
    panels = []
    for (rx, ry, rw, rh) in rects:
        frame = NSMakeRect(rx, ry, rw, rh)
        p = _make_panel(frame, ak=ak, color_rgb=_HUD_RED_RGB)
        p.orderFront_(None)
        panels.append(p)
    return panels


# ---------------------------------------------------------------------------
# HUD subprocess entry point
# ---------------------------------------------------------------------------

def run_hud_subprocess() -> None:
    """Run the HUD AppKit event loop.  Called when the module is run directly.

    Reads JSON commands from stdin; maintains RecPillPanel + RegionFramePanel.
    On EOF (parent died) shuts down cleanly via callAfter.
    """
    import atexit
    import sys
    import threading

    ak = _import_appkit_deps()
    NSApplication = ak["NSApplication"]
    NSTimer = ak["NSTimer"]
    NSMakeRect = ak["NSMakeRect"]
    AppHelper = ak["AppHelper"]

    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(4)  # NSApplicationActivationPolicyAccessory

    state = HUDState()
    panels: list = []
    pill_label = None
    timer_ref: list = [None]   # mutable container so the closure can write it
    pill_panel_ref: list = [None]

    def _close_all_panels():
        nonlocal panels, pill_label
        for p in panels:
            try:
                p.close()
            except Exception:
                pass
        panels = []
        pill_label = None
        if timer_ref[0] is not None:
            try:
                timer_ref[0].invalidate()
            except Exception:
                pass
            timer_ref[0] = None
        if pill_panel_ref[0] is not None:
            try:
                pill_panel_ref[0].close()
            except Exception:
                pass
            pill_panel_ref[0] = None

    def _tick(_timer):
        if state.started_at is None or pill_label is None:
            return
        elapsed = int(time.monotonic() - state.started_at)
        pill_label.setStringValue_(f"● REC {format_rec_time(elapsed)}")

    def _on_start(cmd: dict):
        nonlocal panels, pill_label
        _close_all_panels()

        screen_data = cmd.get("screen", {})
        region = cmd.get("region", [0, 0, 100, 100])
        started_at = cmd.get("started_at", time.monotonic())
        state.handle(cmd)

        # Reconstruct ScreenDevice from the dict the parent serialised
        from .screens import ScreenDevice as _SD
        bounds_raw = screen_data.get("bounds", [0, 0, 1920, 1080])
        s_device = _SD(
            av_index=screen_data.get("av_index", 0),
            av_name=screen_data.get("av_name", ""),
            display_id=screen_data.get("display_id", 0),
            bounds=tuple(bounds_raw),
            is_main=screen_data.get("is_main", True),
            backing_scale=screen_data.get("backing_scale", 1.0),
        )

        bx, by, bw, bh = s_device.bounds
        sc = s_device.backing_scale
        screen_appkit = (
            float(bx),
            float(by),
            bw / sc,
            bh / sc,
        )
        crop_appkit = transform_region_to_appkit(tuple(region), s_device)

        # Frame panels
        panels = _make_frame_panels(crop_appkit, ak=ak)

        # Pill panel
        pill_panel, label = _make_rec_pill_panel(crop_appkit, screen_appkit, ak=ak)
        pill_panel_ref[0] = pill_panel
        pill_label = label

        elapsed = int(time.monotonic() - started_at)
        label.setStringValue_(f"● REC {format_rec_time(elapsed)}")
        pill_panel.orderFront_(None)

        # 1-second repeating timer on the main thread.  Use the block API
        # (macOS 10.12+) so the Python `_tick` callable runs every second,
        # updating the label content.  The target+selector form would only
        # redraw with stale content because Python functions are not valid
        # ObjC selectors — CHG-2218 §Scope §1 requires monotonic-clock-derived
        # text per tick.
        state.started_at = started_at
        t = NSTimer.scheduledTimerWithTimeInterval_repeats_block_(
            1.0, True, _tick
        )
        timer_ref[0] = t

    def _on_stop():
        state.handle({"cmd": "stop"})
        _close_all_panels()
        AppHelper.callAfter(app.terminate_, None)

    def _stdin_reader():
        """Background thread: read JSON lines from stdin; dispatch to main thread."""
        try:
            for raw_line in sys.stdin:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    cmd = parse_command(line)
                except ValueError as exc:
                    logger.warning("HUD: bad command %r: %s", line, exc)
                    continue

                if cmd["cmd"] == "start":
                    AppHelper.callAfter(_on_start, cmd)
                elif cmd["cmd"] == "stop":
                    AppHelper.callAfter(_on_stop)
                elif cmd["cmd"] == "status":
                    status_line = json.dumps({"status": state.state}) + "\n"
                    sys.stdout.write(status_line)
                    sys.stdout.flush()
        except Exception as exc:
            logger.warning("HUD stdin reader error: %s", exc)
        finally:
            # EOF or error → parent died → shut down
            AppHelper.callAfter(app.terminate_, None)

    atexit.register(_close_all_panels)

    t = threading.Thread(target=_stdin_reader, daemon=True)
    t.start()

    try:
        AppHelper.runEventLoop()
    finally:
        _close_all_panels()


# ---------------------------------------------------------------------------
# Module entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    run_hud_subprocess()
