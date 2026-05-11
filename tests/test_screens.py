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
    """Return a mock Quartz module with n_displays active displays."""
    quartz = MagicMock()
    display_ids = list(range(1001, 1001 + n_displays))
    quartz.CGGetActiveDisplayList.return_value = display_ids
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
    appkit = _make_appkit_mock(quartz.CGGetActiveDisplayList.return_value)

    with (
        patch("screen_harness.screens._import_quartz", return_value=quartz),
        patch("screen_harness.screens._import_appkit", return_value=appkit),
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
