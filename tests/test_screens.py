"""Unit tests for screen_harness.screens — locale-independent probe + resolve."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from screen_harness.admin import parse_avfoundation_devices
from screen_harness.screens import (
    PickedScreen,
    ScreenDevice,
    ScreenProbeError,
    probe_screens,
    resolve_screen,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "avfoundation_devices"
SCHEMA_PATH = Path(__file__).parent / "fixtures" / "picked_screen.schema.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_quartz_mock(n_displays: int = 1) -> MagicMock:
    """Return a mock Quartz module with n_displays active displays.

    `CGGetActiveDisplayList` in PyObjC uses C out-parameters, exposed as
    `CGGetActiveDisplayList(maxDisplays, None, None) -> (err, ids, count)`.
    The mock returns the same shape — anything else would let bugs like the
    single-arg call (caught by Codex bot as P1) sneak past unit tests.
    """
    quartz = MagicMock()
    display_ids = list(range(1001, 1001 + n_displays))
    quartz.CGGetActiveDisplayList.return_value = (0, display_ids, n_displays)
    quartz.CGMainDisplayID.return_value = display_ids[0]
    quartz.CGDisplayBounds.side_effect = lambda did: _bounds_for_id(did, display_ids)
    quartz.CGRectGetMinX.side_effect = lambda r: r[0]
    quartz.CGRectGetMinY.side_effect = lambda r: r[1]
    quartz.CGRectGetWidth.side_effect = lambda r: r[2]
    quartz.CGRectGetHeight.side_effect = lambda r: r[3]
    return quartz


def _bounds_for_id(did: int, all_ids: list[int]) -> tuple:
    idx = all_ids.index(did)
    return (idx * 2560, 0, 2560, 1600)


def _make_appkit_mock(display_ids: list[int]) -> MagicMock:
    appkit = MagicMock()
    screens = []
    for i, did in enumerate(display_ids):
        s = MagicMock()
        s.deviceDescription.return_value = {"NSScreenNumber": did}
        s.backingScaleFactor.return_value = 2.0
        screens.append(s)
    appkit.NSScreen.screens.return_value = screens
    return appkit


# ---------------------------------------------------------------------------
# probe_screens parses each locale fixture (5 tests)
# ---------------------------------------------------------------------------

def _probe_from_fixture(locale: str) -> list[ScreenDevice]:
    fixture_text = (FIXTURES_DIR / f"{locale}.txt").read_text()
    devices = parse_avfoundation_devices(fixture_text)
    n_video = len(devices.video)
    n_displays = 1  # each fixture has exactly 1 screen device
    quartz = _make_quartz_mock(n_displays=n_displays)
    # CGGetActiveDisplayList now returns (err, ids, count); pull ids out for the AppKit mock.
    _err, display_ids, _count = quartz.CGGetActiveDisplayList.return_value
    appkit = _make_appkit_mock(display_ids)

    with (
        patch("screen_harness.screens._import_quartz", return_value=quartz),
        patch("screen_harness.screens._import_appkit", return_value=appkit),
        patch("screen_harness.screens._import_avfoundation", return_value=MagicMock()),
        patch("screen_harness.screens._count_av_devices_before_screens", return_value=n_video - n_displays),
        patch("screen_harness.screens.list_avfoundation_devices", return_value=(devices, None)),
    ):
        return probe_screens()


def test_probe_screens_parses_en():
    screens = _probe_from_fixture("en")
    assert len(screens) == 1
    assert screens[0].av_index == 1
    assert "FaceTime" not in screens[0].av_name


def test_probe_screens_parses_zh():
    screens = _probe_from_fixture("zh")
    assert len(screens) == 1
    assert screens[0].av_index == 1
    assert screens[0].is_main is True


def test_probe_screens_parses_ja():
    screens = _probe_from_fixture("ja")
    assert len(screens) == 1
    assert screens[0].av_index == 1


def test_probe_screens_parses_es():
    screens = _probe_from_fixture("es")
    assert len(screens) == 1
    assert screens[0].av_index == 1


def test_probe_screens_parses_fr():
    screens = _probe_from_fixture("fr")
    assert len(screens) == 1
    assert screens[0].av_index == 1


# ---------------------------------------------------------------------------
# resolve_screen — default picks main
# ---------------------------------------------------------------------------

def _make_screen_device(
    *,
    av_index: int,
    av_name: str = "Capture screen 0",
    display_id: int = 1001,
    bounds: tuple = (0, 0, 2560, 1600),
    is_main: bool = True,
    backing_scale: float = 2.0,
) -> ScreenDevice:
    return ScreenDevice(
        av_index=av_index,
        av_name=av_name,
        display_id=display_id,
        bounds=bounds,
        is_main=is_main,
        backing_scale=backing_scale,
    )


def _patch_probe(screens: list[ScreenDevice]):
    return patch("screen_harness.screens.probe_screens", return_value=screens)


def test_resolve_screen_default_picks_main():
    main_screen = _make_screen_device(av_index=1, is_main=True)
    with _patch_probe([main_screen]):
        picked = resolve_screen(None)
    assert picked.device is main_screen
    assert picked.reason == "default-main"


def test_resolve_screen_explicit_int_rejects_camera():
    """Passing int 0 when 0 is a camera raises ValueError with helpful message."""
    camera_idx = 0
    screen_device = _make_screen_device(av_index=1)
    # av_index 0 is not in the screens list → it's a camera
    with _patch_probe([screen_device]):
        with pytest.raises(ValueError, match="camera"):
            resolve_screen(camera_idx)


def test_resolve_screen_explicit_int_picks_screen():
    screen_device = _make_screen_device(av_index=2)
    with _patch_probe([screen_device]):
        picked = resolve_screen(2)
    assert picked.device is screen_device
    assert picked.reason == "explicit-int:2"


def test_resolve_screen_display_pos_1_indexed():
    """display:1 picks the first ScreenDevice (1-indexed)."""
    screen_a = _make_screen_device(av_index=1, display_id=1001, is_main=True)
    screen_b = _make_screen_device(av_index=2, av_name="Capture screen 1", display_id=1002, is_main=False)
    with _patch_probe([screen_a, screen_b]):
        picked = resolve_screen("display:1")
    assert picked.device is screen_a
    assert picked.reason == "display-pos:1"


def test_resolve_screen_display_pos_out_of_range_raises():
    screen_device = _make_screen_device(av_index=1)
    with _patch_probe([screen_device]):
        with pytest.raises((IndexError, ValueError)):
            resolve_screen("display:99")


def test_resolve_screen_auto_app_not_running_falls_back_to_main_with_warning(caplog):
    """app not running → warning + main fallback."""
    import logging
    main_screen = _make_screen_device(av_index=1, is_main=True)
    with _patch_probe([main_screen]):
        with patch("screen_harness.screens._get_app_window_center", return_value=None):
            with caplog.at_level(logging.WARNING, logger="screen_harness"):
                picked = resolve_screen(None, app="NotRunningApp")
    assert picked.device is main_screen
    assert "fallback-main" in picked.reason


# ---------------------------------------------------------------------------
# JSON schema round-trip
# ---------------------------------------------------------------------------

def test_picked_screen_json_schema_roundtrip():
    """Serialize a PickedScreen to dict and validate against the JSON schema."""
    schema = json.loads(SCHEMA_PATH.read_text())
    device = _make_screen_device(av_index=1)
    picked = PickedScreen(device=device, reason="default-main")
    blob = asdict(device) | {"reason": picked.reason}

    # Validate required keys
    for key in schema["required"]:
        assert key in blob, f"missing key: {key}"

    # Validate types for each property
    props = schema["properties"]
    assert isinstance(blob["av_index"], int)
    assert isinstance(blob["av_name"], str)
    assert isinstance(blob["display_id"], int)
    assert isinstance(blob["bounds"], (list, tuple)) and len(blob["bounds"]) == 4
    assert isinstance(blob["is_main"], bool)
    assert isinstance(blob["backing_scale"], float)
    assert isinstance(blob["reason"], str)


# ---------------------------------------------------------------------------
# R2 review fixes: auto-front-app happy path + osascript injection guard
# ---------------------------------------------------------------------------

def test_get_app_window_center_happy_path():
    """_get_app_window_center parses osascript output to (cx, cy)."""
    from screen_harness import screens as screens_mod
    fake = MagicMock(returncode=0, stdout="400,300\n", stderr="")
    with patch.object(screens_mod.subprocess, "run", return_value=fake):
        result = screens_mod._get_app_window_center("Safari")
    assert result == (400, 300)


def test_get_app_window_center_rejects_injection_names():
    """App names with osascript-injection-capable chars are refused without invoking subprocess."""
    from screen_harness import screens as screens_mod
    with patch.object(screens_mod.subprocess, "run") as run_mock:
        for bad in [
            'Safari"\nset x to do shell script "rm -rf"',  # quote + newline injection
            "Safari;ls",                                    # semicolon
            'Safari" & "evil',                              # quote splice
            "A" * 65,                                       # too long
            "",                                             # empty
        ]:
            assert screens_mod._get_app_window_center(bad) is None
        run_mock.assert_not_called()


def test_get_app_window_center_not_running_returns_none():
    from screen_harness import screens as screens_mod
    fake = MagicMock(returncode=0, stdout="NOTRUNNING\n", stderr="")
    with patch.object(screens_mod.subprocess, "run", return_value=fake):
        assert screens_mod._get_app_window_center("Safari") is None


def test_resolve_screen_auto_front_app_picks_second_display():
    """auto:<App> happy path: window centre inside second screen's bounds → pick screen 2."""
    fixture = (FIXTURES_DIR / "en.txt").read_text()
    quartz = _make_quartz_mock(n_displays=2)
    # Display 0 at (0,0,1920,1080); display 1 at (1920,0,1920,1080) (side-by-side).
    quartz.CGDisplayBounds.side_effect = lambda did: {
        1001: (0, 0, 1920, 1080),
        1002: (1920, 0, 1920, 1080),
    }[did]

    appkit = MagicMock()
    appkit.NSScreen.screens.return_value = []  # no NSScreen lookups needed

    with patch("screen_harness.screens._import_quartz", return_value=quartz), \
         patch("screen_harness.screens._import_appkit", return_value=appkit), \
         patch("screen_harness.screens._import_avfoundation", return_value=MagicMock()), \
         patch("screen_harness.screens._count_av_devices_before_screens", return_value=1), \
         patch(
             "screen_harness.screens.list_avfoundation_devices",
             return_value=(parse_avfoundation_devices(_two_screen_fixture()), None),
         ), \
         patch(
             "screen_harness.screens._get_app_window_center",
             return_value=(2500, 540),  # inside display 1002's bounds
         ):
        picked = resolve_screen(None, app="Safari")

    assert picked.reason == "auto-front-app:Safari"
    assert picked.device.display_id == 1002
    assert picked.device.av_index == 2  # one camera + two screens → screens at idx 1 and 2


def _two_screen_fixture() -> str:
    """One camera + two screens — for the auto-front-app multi-display test."""
    return (
        "[AVFoundation indev @ 0x100] AVFoundation video devices:\n"
        "[AVFoundation indev @ 0x100] [0] FaceTime HD Camera\n"
        "[AVFoundation indev @ 0x100] [1] Capture screen 0\n"
        "[AVFoundation indev @ 0x100] [2] Capture screen 1\n"
        "[AVFoundation indev @ 0x100] AVFoundation audio devices:\n"
    )


# ---------------------------------------------------------------------------
# Codex bot R1 findings (PR #5)
# ---------------------------------------------------------------------------

def test_probe_screens_refuses_without_pyobjc():
    """Codex P1/P2 rounds 2 & 4: degraded mode must always refuse — the
    'screens come last' convention is unsafe in the presence of virtual or
    Continuity cameras, and Screen Harness should fail closed rather than
    risk recording a camera."""
    from screen_harness import screens as screens_mod
    from screen_harness.admin import AVFoundationDevices

    devices = AVFoundationDevices(
        video=[
            {"index": "0", "name": "FaceTime HD Camera"},
            {"index": "1", "name": "Continuity Camera"},
            {"index": "2", "name": "Capture screen 0"},  # even with a real screen
        ],
        audio=[],
    )
    with patch.object(screens_mod, "_import_quartz", side_effect=ImportError("no pyobjc")), \
         patch.object(screens_mod, "list_avfoundation_devices", return_value=(devices, None)):
        with pytest.raises(ScreenProbeError, match="PyObjC is required"):
            probe_screens()


def test_probe_screens_refuses_when_only_avfoundation_pyobjc_missing():
    """Codex P2 on PR #14: when Quartz/Cocoa are installed but
    pyobjc-framework-AVFoundation is missing, probe_screens must still
    fail closed via ScreenProbeError — not leak ModuleNotFoundError
    from _count_av_devices_before_screens()."""
    from screen_harness import screens as screens_mod
    from screen_harness.admin import AVFoundationDevices

    devices = AVFoundationDevices(
        video=[
            {"index": "0", "name": "FaceTime HD Camera"},
            {"index": "1", "name": "Capture screen 0"},
        ],
        audio=[],
    )
    with patch.object(screens_mod, "_import_avfoundation", side_effect=ImportError("no AVFoundation")), \
         patch.object(screens_mod, "list_avfoundation_devices", return_value=(devices, None)):
        with pytest.raises(ScreenProbeError, match="PyObjC is required"):
            probe_screens()


def test_probe_screens_calls_CGGetActiveDisplayList_with_out_params():
    """Codex P1 regression: probe_screens must call the 3-arg form and
    handle the (err, ids, count) tuple. Single-arg call raises TypeError on
    real PyObjC."""
    fixture = (FIXTURES_DIR / "en.txt").read_text()
    quartz = _make_quartz_mock(n_displays=1)
    appkit = _make_appkit_mock([1001])
    from screen_harness.admin import parse_avfoundation_devices
    with patch("screen_harness.screens._import_quartz", return_value=quartz), \
         patch("screen_harness.screens._import_appkit", return_value=appkit), \
         patch("screen_harness.screens._import_avfoundation", return_value=MagicMock()), \
         patch("screen_harness.screens._count_av_devices_before_screens", return_value=1), \
         patch(
             "screen_harness.screens.list_avfoundation_devices",
             return_value=(parse_avfoundation_devices(fixture), None),
         ):
        screens = probe_screens()
    # Verify it was called with the OUT-PARAMETER signature.
    quartz.CGGetActiveDisplayList.assert_called_with(16, None, None)
    assert len(screens) == 1
    assert screens[0].display_id == 1001


def test_start_recording_propagates_probe_failure_no_camera_fallback():
    """Codex bot P1 (round 2): probe failure must not silently fall back to
    recording from AVFoundation index 0."""
    from screen_harness import helpers
    helpers.configure(Path("/tmp/sh-codex-p1-test"))
    with patch("screen_harness.screens.probe_screens",
               side_effect=ScreenProbeError("simulated probe failure")):
        with pytest.raises(ScreenProbeError, match="simulated probe failure"):
            helpers.start_recording("camera_safety_regression")


def test_probe_screens_refuses_when_avfoundation_lists_only_cameras():
    """Codex P1 (round 3): if FFmpeg shows only the camera (Screen Recording
    permission missing) but Quartz reports a display, refuse with permission
    guidance — do NOT bind the camera to the display."""
    from screen_harness import screens as screens_mod
    from screen_harness.admin import AVFoundationDevices

    only_camera = AVFoundationDevices(
        video=[{"index": "0", "name": "FaceTime HD Camera"}],
        audio=[],
    )
    quartz = _make_quartz_mock(n_displays=1)  # Quartz sees a real display
    appkit = _make_appkit_mock([1001])
    with patch.object(screens_mod, "_import_quartz", return_value=quartz), \
         patch.object(screens_mod, "_import_appkit", return_value=appkit), \
         patch.object(screens_mod, "_import_avfoundation", return_value=MagicMock()), \
         patch.object(screens_mod, "_count_av_devices_before_screens", return_value=1), \
         patch.object(screens_mod, "list_avfoundation_devices", return_value=(only_camera, None)):
        with pytest.raises(ScreenProbeError, match="Screen Recording permission"):
            probe_screens()


def test_probe_screens_handles_muxed_device_offset():
    """Codex P1 (round 5): HDMI/USB capture cards are AVMediaTypeMuxed and
    appear in FFmpeg's video-section index before screens. The offset must
    include them or screens at indices > N_cameras get mis-bound (or
    expected_screens becomes too large and probe refuses)."""
    from screen_harness import screens as screens_mod
    from screen_harness.admin import AVFoundationDevices

    # 1 camera + 1 muxed capture card + 1 screen → indices [0..2]
    devices = AVFoundationDevices(
        video=[
            {"index": "0", "name": "FaceTime HD Camera"},
            {"index": "1", "name": "Cam Link 4K"},        # AVMediaTypeMuxed
            {"index": "2", "name": "Capture screen 0"},
        ],
        audio=[],
    )
    quartz = _make_quartz_mock(n_displays=1)
    appkit = _make_appkit_mock([1001])
    # _count_av_devices_before_screens returns 2 (1 video + 1 muxed)
    with patch.object(screens_mod, "_import_quartz", return_value=quartz), \
         patch.object(screens_mod, "_import_appkit", return_value=appkit), \
         patch.object(screens_mod, "_import_avfoundation", return_value=MagicMock()), \
         patch.object(screens_mod, "_count_av_devices_before_screens", return_value=2), \
         patch.object(screens_mod, "list_avfoundation_devices", return_value=(devices, None)):
        screens = probe_screens()
    assert len(screens) == 1
    assert screens[0].av_index == 2  # skipped past camera (0) and muxed (1)
    assert screens[0].av_name == "Capture screen 0"


def test_resolve_screen_auto_prefix_routes_to_app_resolution():
    """Codex P2 round 7: `screen="auto:Safari"` is documented in PRP §Scope
    and must reach the app-window-center path."""
    main_screen = _make_screen_device(av_index=1, is_main=True, bounds=(0, 0, 1920, 1080))
    with _patch_probe([main_screen]):
        with patch("screen_harness.screens._get_app_window_center", return_value=(500, 500)):
            picked = resolve_screen("auto:Safari")
    assert picked.reason == "auto-front-app:Safari"


def test_resolve_screen_auto_prefix_empty_app_name_raises():
    main_screen = _make_screen_device(av_index=1, is_main=True)
    with _patch_probe([main_screen]):
        with pytest.raises(ValueError, match="auto: spec requires an app name"):
            resolve_screen("auto:")
