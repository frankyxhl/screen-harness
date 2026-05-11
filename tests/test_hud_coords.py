"""Unit tests for HUD coordinate transform (pure Python, no AppKit).

Tests the transform_region_to_appkit function that converts picked-screen
pixel coordinates (top-left origin) to AppKit point coordinates
(bottom-left origin, global AppKit space).
"""

from __future__ import annotations

import pytest

from screen_harness.hud import transform_region_to_appkit
from screen_harness.screens import ScreenDevice


def _make_screen(
    *,
    av_index: int = 0,
    av_name: str = "Capture screen 0",
    display_id: int = 1,
    bounds: tuple[int, int, int, int],
    is_main: bool = True,
    backing_scale: float,
) -> ScreenDevice:
    return ScreenDevice(
        av_index=av_index,
        av_name=av_name,
        display_id=display_id,
        bounds=bounds,
        is_main=is_main,
        backing_scale=backing_scale,
    )


class TestTransform1x1080p:
    """1× 1080p main display at origin (0, 0)."""

    def setup_method(self):
        self.screen = _make_screen(
            bounds=(0, 0, 1920, 1080),
            backing_scale=1.0,
        )
        self.region = (100, 100, 800, 600)

    def test_x(self):
        x, y, w, h = transform_region_to_appkit(self.region, self.screen)
        assert x == 100.0

    def test_y(self):
        x, y, w, h = transform_region_to_appkit(self.region, self.screen)
        # appkit_y = 0 + (1080 - (100 + 600) / 1.0) = 1080 - 700 = 380
        assert y == 380.0

    def test_w(self):
        x, y, w, h = transform_region_to_appkit(self.region, self.screen)
        assert w == 800.0

    def test_h(self):
        x, y, w, h = transform_region_to_appkit(self.region, self.screen)
        assert h == 600.0

    def test_full_result(self):
        result = transform_region_to_appkit(self.region, self.screen)
        assert result == (100.0, 380.0, 800.0, 600.0)


class TestTransformRetina2x:
    """2880×1800 Retina @2x main display at origin (0, 0).

    Physical pixel region (200, 200, 1600, 1200) maps to logical points
    by dividing by backing_scale=2.0.
    """

    def setup_method(self):
        self.screen = _make_screen(
            bounds=(0, 0, 2880, 1800),
            backing_scale=2.0,
        )
        self.region = (200, 200, 1600, 1200)

    def test_full_result(self):
        x, y, w, h = transform_region_to_appkit(self.region, self.screen)
        # screen height in AppKit points = 1800/2 = 900
        # appkit_x = 0 + 200/2 = 100.0
        # appkit_y = 0 + (900 - (200+1200)/2) = 900 - 700 = 200.0
        # appkit_w = 1600/2 = 800.0
        # appkit_h = 1200/2 = 600.0
        assert x == 100.0
        assert y == 200.0
        assert w == 800.0
        assert h == 600.0


class TestTransformDualScreen:
    """Side-by-side dual screen: 1080p at (0,0), Retina at (1920,0).

    Region is on the Retina screen, starting at global pixel x=2120
    (1920 + 200 offset within that screen).
    """

    def setup_method(self):
        self.main_screen = _make_screen(
            av_index=0,
            bounds=(0, 0, 1920, 1080),
            backing_scale=1.0,
        )
        self.retina_screen = _make_screen(
            av_index=1,
            display_id=2,
            bounds=(1920, 0, 2880, 1800),
            is_main=False,
            backing_scale=2.0,
        )
        # Region is 200px into the Retina screen at global coords (2120, 100)
        self.region = (200, 100, 800, 600)

    def test_retina_region(self):
        x, y, w, h = transform_region_to_appkit(self.region, self.retina_screen)
        # AppKit space: retina screen origin is at (1920, 0) in AppKit points
        # (the bounds x=1920 is already in points for the CGDisplayBounds)
        # appkit_x = 1920 + 200/2 = 1920 + 100 = 2020.0
        # screen AppKit height = 1800/2 = 900
        # appkit_y = 0 + (900 - (100+600)/2) = 900 - 350 = 550.0
        # appkit_w = 800/2 = 400.0
        # appkit_h = 600/2 = 300.0
        assert x == 2020.0
        assert y == 550.0
        assert w == 400.0
        assert h == 300.0

    def test_main_screen_region(self):
        region = (100, 100, 800, 600)
        x, y, w, h = transform_region_to_appkit(region, self.main_screen)
        # backing_scale=1.0, origin at (0, 0)
        # appkit_x = 0 + 100/1 = 100.0
        # appkit_y = 0 + (1080 - (100+600)/1) = 1080 - 700 = 380.0
        assert x == 100.0
        assert y == 380.0
        assert w == 800.0
        assert h == 600.0
