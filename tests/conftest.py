"""Pytest fixtures.

`stub_screen_resolution` autouse fixture preloads a fake `ScreenDevice` into
`helpers._STATE.screen_inventory` and patches `resolve_screen` so that the
many `start_recording` tests in `test_helpers_mvp.py` don't have to invoke
the real `probe_screens` (which on Linux CI cannot succeed: no PyObjC, no
AVFoundation).

Tests that want to exercise the real probe/resolve path (`test_screens.py`,
`test_screens_invariant.py`) bypass this fixture by stubbing
`screen_harness.screens` directly inside the test body.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from screen_harness.screens import PickedScreen, ScreenDevice


_FAKE_SCREEN = ScreenDevice(
    av_index=0,
    av_name="Capture screen 0",
    display_id=12345,
    bounds=(0, 0, 1920, 1080),
    is_main=True,
    backing_scale=2.0,
)
_FAKE_PICK = PickedScreen(device=_FAKE_SCREEN, reason="default-main")


@pytest.fixture(autouse=True)
def stub_screen_resolution(request):
    """Bypass real probe_screens / resolve_screen for non-screen tests.

    Tests in test_screens*.py exercise the real functions and opt out by
    file path. Everywhere else (helpers, recorder, …) gets a stable fake.
    """
    if "test_screens" in request.node.fspath.basename or "test_hud" in request.node.fspath.basename:
        yield
        return
    with patch("screen_harness.screens.probe_screens", return_value=[_FAKE_SCREEN]), \
         patch("screen_harness.screens.resolve_screen", return_value=_FAKE_PICK):
        yield
