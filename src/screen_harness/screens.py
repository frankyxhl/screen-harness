"""Smart screen selection: probe AVFoundation devices and resolve a recording target.

Detection algorithm is locale-independent (count-based, not name-based):
  camera_count = N_video_devices - N_active_displays
  screen k has av_index = camera_count + k

PyObjC (Quartz + AppKit) is a soft dependency.  When absent the module degrades
to "main display only" mode: display_id=-1 sentinel, bounds=(0,0,0,0), backing_scale=1.0.
Auto-app resolution (app= kwarg) raises ScreenProbeError without PyObjC.
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass

from .admin import list_avfoundation_devices

logger = logging.getLogger("screen_harness")


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ScreenDevice:
    av_index: int                        # FFmpeg avfoundation -i N
    av_name: str                         # raw locale-dependent device name
    display_id: int                      # CGDirectDisplayID (0 = kCGNullDirectDisplay → camera-rejection sentinel; -1 = PyObjC-absent unknown but trust av_index)
    bounds: tuple[int, int, int, int]    # x, y, w, h in global pixel coords
    is_main: bool
    backing_scale: float


@dataclass(frozen=True)
class PickedScreen:
    device: ScreenDevice
    reason: str  # "default-main" | "explicit-int:N" | "display-pos:N"
                 # | "auto-front-app:AppName"
                 # | "auto-no-app-no-front-window:fallback-main"


class ScreenProbeError(Exception):
    """Raised when screen enumeration fails and cannot be recovered."""


# ---------------------------------------------------------------------------
# Lazy PyObjC imports
# ---------------------------------------------------------------------------

def _import_quartz():
    import Quartz
    return Quartz


def _import_appkit():
    import AppKit
    return AppKit


def _import_avfoundation():
    import AVFoundation
    return AVFoundation


def _count_av_devices_before_screens() -> int:
    """Count AVFoundation capture devices that FFmpeg lists *before* screens.

    FFmpeg's avfoundation indev orders its `[N]` indices as:
      [0..N_video-1]                          AVMediaTypeVideo (cameras)
      [N_video..N_video+N_muxed-1]            AVMediaTypeMuxed (HDMI/USB cap.)
      [N_video+N_muxed..]                     Capture screen N

    Screens are NOT AVCaptureDevices (they come from AVCaptureScreenInput +
    CGDirectDisplayID), so we count cameras + muxed devices structurally via
    AVFoundation, independent of FFmpeg's permission-dependent view. This is
    the "things to skip past" offset for the screen binding.

    Codex bot finding P1 (round 5): without the muxed term, hosts with
    HDMI/USB capture hardware (e.g. Elgato Cam Link) inflate
    `expected_screens` and probe_screens refuses to record even though real
    screen devices are present.
    """
    av = _import_avfoundation()
    cameras = av.AVCaptureDevice.devicesWithMediaType_(av.AVMediaTypeVideo)
    muxed = av.AVCaptureDevice.devicesWithMediaType_(av.AVMediaTypeMuxed)
    return int(len(cameras)) + int(len(muxed))


# ---------------------------------------------------------------------------
# Core probe
# ---------------------------------------------------------------------------

def probe_screens(*, ffmpeg: str = "ffmpeg") -> list[ScreenDevice]:
    """Return a list of ScreenDevice objects for every active display.

    Uses a count-based algorithm (locale-independent):
      camera_count = N_video_devices - N_active_displays
      screen k  →  av_index = camera_count + k

    Falls back to a single dummy main-display entry when PyObjC is absent.
    """
    av_devices, _err = list_avfoundation_devices(ffmpeg)
    n_video = len(av_devices.video)

    try:
        quartz = _import_quartz()
        appkit = _import_appkit()
    except ImportError:
        # Fail closed.  Without PyObjC there is no structural signal to
        # distinguish a screen device from a camera (the "screens come last"
        # convention breaks once virtual/Continuity cameras are installed —
        # Codex bot finding P1 round 4).  Refuse and tell the user how to
        # fix it; never silently risk recording the camera.
        raise ScreenProbeError(
            "PyObjC is required to safely identify screen capture devices.  "
            "Install with `pip install 'screen-harness[macos]'` (or "
            "`uv sync --group dev` for development).  Without PyObjC there is "
            "no structural way to tell an AVFoundation camera apart from a "
            "screen device, and Screen Harness refuses to guess."
        )

    # CGGetActiveDisplayList uses C out-parameters; PyObjC exposes it as
    # `(maxDisplays, None, None) -> (err, activeDisplays, count)`.  Calling
    # with a single argument raises TypeError — Codex bot finding P1.
    err, display_ids_raw, count = quartz.CGGetActiveDisplayList(16, None, None)
    if err != 0:
        raise ScreenProbeError(f"CGGetActiveDisplayList returned error {err}")
    display_ids: list[int] = list(display_ids_raw)[: int(count)]
    n_displays = len(display_ids)

    # Offset derived from AVFoundation directly (structural truth) rather
    # than inferred from `n_video - n_displays`.  Inference is unsafe: when
    # Screen Recording permission is missing, FFmpeg silently omits screen
    # devices but Quartz still reports displays, so the inferred offset
    # drops to 0 and the camera at AV index 0 gets bound to a real display
    # (Codex P1 round 3).  Includes AVMediaTypeMuxed so HDMI/USB capture
    # hardware doesn't inflate `expected_screens` (Codex P1 round 5).
    camera_count = _count_av_devices_before_screens()
    expected_screens = n_video - camera_count
    if expected_screens != n_displays:
        raise ScreenProbeError(
            f"AVFoundation reports {n_video} video-section device(s) "
            f"({camera_count} camera/muxed, {expected_screens} non-camera entries) "
            f"but Quartz reports {n_displays} active display(s). "
            "FFmpeg is probably missing Screen Recording permission — grant it "
            "in System Settings → Privacy & Security → Screen & System Audio Recording."
        )

    main_display_id: int = quartz.CGMainDisplayID()

    # Build a dict from NSScreenNumber → NSScreen for backing scale lookup.
    ns_screens: dict[int, object] = {}
    for ns in appkit.NSScreen.screens():
        did = ns.deviceDescription().get("NSScreenNumber")
        if did is not None:
            ns_screens[int(did)] = ns

    screens: list[ScreenDevice] = []
    for k, display_id in enumerate(display_ids):
        av_index = camera_count + k
        if av_index >= n_video:
            break
        av_entry = av_devices.video[av_index]
        rect = quartz.CGDisplayBounds(display_id)
        x = int(quartz.CGRectGetMinX(rect))
        y = int(quartz.CGRectGetMinY(rect))
        w = int(quartz.CGRectGetWidth(rect))
        h = int(quartz.CGRectGetHeight(rect))

        ns = ns_screens.get(int(display_id))
        backing_scale = float(ns.backingScaleFactor()) if ns is not None else 1.0

        screens.append(
            ScreenDevice(
                av_index=av_index,
                av_name=av_entry["name"],
                display_id=int(display_id),
                bounds=(x, y, w, h),
                is_main=(int(display_id) == int(main_display_id)),
                backing_scale=backing_scale,
            )
        )

    return screens


# ---------------------------------------------------------------------------
# Resolve
# ---------------------------------------------------------------------------

def resolve_screen(
    spec,
    *,
    app: str | None = None,
    ffmpeg: str = "ffmpeg",
) -> PickedScreen:
    """Resolve a recording screen from *spec* and optional *app* name.

    spec:
      None          → main display (unless app= overrides)
      int n         → validate that av_index n is a screen; raise ValueError if camera
      "display:k"   → 1-indexed position among ScreenDevice list

    app:
      str           → resolve to the display whose bounds contain the app's
                      front window centre.  Falls back to main with warning if
                      the app is not running or has no front window.
    """
    screens = probe_screens(ffmpeg=ffmpeg)

    if not screens:
        raise ScreenProbeError("No screen devices found — check Screen Recording permission.")

    def _main() -> ScreenDevice:
        for s in screens:
            if s.is_main:
                return s
        return screens[0]

    # spec="auto:<AppName>" — documented in PRP-2213 §Scope as the agent-facing
    # shorthand.  Route to the same path as app=<AppName>.  Codex P2 round 7.
    if isinstance(spec, str) and spec.startswith("auto:"):
        spec_app = spec[len("auto:"):].strip()
        if not spec_app:
            raise ValueError("auto: spec requires an app name (e.g. 'auto:Safari')")
        app = spec_app
        spec = None

    # app= resolution
    if app is not None and spec is None:
        center = _get_app_window_center(app)
        if center is None:
            logger.warning(
                "App %r is not running or has no front window — "
                "falling back to main display.",
                app,
            )
            return PickedScreen(
                device=_main(),
                reason=f"auto-no-app-no-front-window:fallback-main",
            )
        cx, cy = center
        for s in screens:
            x, y, w, h = s.bounds
            if x <= cx < x + w and y <= cy < y + h:
                return PickedScreen(device=s, reason=f"auto-front-app:{app}")
        # Window centre not within any known display → fall back to main
        logger.warning(
            "App %r window centre (%d, %d) not within any known display bounds — "
            "falling back to main display.",
            app, cx, cy,
        )
        return PickedScreen(device=_main(), reason=f"auto-no-app-no-front-window:fallback-main")

    # spec=None, no app → default main
    if spec is None:
        return PickedScreen(device=_main(), reason="default-main")

    # spec=int → validate it's a screen
    if isinstance(spec, int):
        screen_indices = {s.av_index for s in screens}
        if spec not in screen_indices:
            raise ValueError(
                f"AVFoundation device index {spec} is not a screen device "
                f"(known screen indices: {sorted(screen_indices)}). "
                f"It may be a camera. Use probe_screens() to list available screens."
            )
        for s in screens:
            if s.av_index == spec:
                return PickedScreen(device=s, reason=f"explicit-int:{spec}")
        # unreachable
        raise ValueError(f"Index {spec} not found among screen devices")  # pragma: no cover

    # spec="display:k" → 1-indexed
    if isinstance(spec, str) and spec.startswith("display:"):
        try:
            k = int(spec.split(":", 1)[1])
        except ValueError:
            raise ValueError(f"Invalid display spec: {spec!r}; expected 'display:N' with N an integer")
        if k < 1 or k > len(screens):
            raise IndexError(
                f"display:{k} out of range — only {len(screens)} screen(s) available (1-indexed)"
            )
        return PickedScreen(device=screens[k - 1], reason=f"display-pos:{k}")

    raise ValueError(f"Unrecognised screen spec: {spec!r}")


# ---------------------------------------------------------------------------
# App window helpers
# ---------------------------------------------------------------------------

_APP_NAME_RE = __import__("re").compile(r"^[A-Za-z0-9 ._&'-]{1,64}$")


def _get_app_window_center(app_name: str) -> tuple[int, int] | None:
    """Return (cx, cy) of the front window of *app_name* via AppleScript.

    Returns None if the app is not running, has no front window, or if
    osascript is unavailable / denies Automation permission.

    Rejects names containing characters outside `[A-Za-z0-9 ._&'-]` to
    prevent AppleScript injection through the embedded string literal.
    """
    if not _APP_NAME_RE.match(app_name):
        logger.warning(
            "App name %r rejected: must match %s", app_name, _APP_NAME_RE.pattern
        )
        return None
    script = (
        f'tell application "System Events"\n'
        f'  if not (exists process "{app_name}") then return "NOTRUNNING"\n'
        f'end tell\n'
        f'tell application "{app_name}"\n'
        f'  set w to window 1\n'
        f'  set {{x, y}} to position of w\n'
        f'  set {{wd, ht}} to size of w\n'
        f'  return (x + wd div 2) & "," & (y + ht div 2)\n'
        f'end tell'
    )
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("osascript failed for app %r: %s", app_name, exc)
        return None

    if result.returncode != 0 or result.stdout.strip() in {"NOTRUNNING", ""}:
        return None

    try:
        parts = result.stdout.strip().split(",")
        return int(parts[0].strip()), int(parts[1].strip())
    except (ValueError, IndexError):
        return None
