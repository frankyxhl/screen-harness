"""Unit tests for HUD coordinate transform (pure Python, no AppKit).

Tests the transform_region_to_appkit function that converts picked-screen
pixel coordinates (top-left origin) to AppKit point coordinates
(bottom-left origin, global AppKit space).
"""

from __future__ import annotations

import pytest

from screen_harness.hud import compute_frame_stroke_rects, transform_region_to_appkit
from screen_harness.screens import ScreenDevice


def _make_screen(
    *,
    av_index: int = 0,
    av_name: str = "Capture screen 0",
    display_id: int = 1,
    bounds: tuple[int, int, int, int],
    is_main: bool = True,
    backing_scale: float,
    appkit_origin: tuple[float, float] | None = None,
    appkit_size: tuple[float, float] | None = None,
) -> ScreenDevice:
    s = backing_scale
    bx, by, bw, bh = bounds
    return ScreenDevice(
        av_index=av_index,
        av_name=av_name,
        display_id=display_id,
        bounds=bounds,
        is_main=is_main,
        backing_scale=s,
        appkit_origin=appkit_origin if appkit_origin is not None else (bx / s, by / s),
        appkit_size=appkit_size if appkit_size is not None else (bw / s, bh / s),
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


class TestTransformDualScreenMixedDPI:
    """Mixed-DPI dual-screen layout.

    Built-in Retina @2x: pixel bounds (0,0,2880,1800), appkit_origin=(0,0),
    appkit_size=(1440,900), backing_scale=2.0.

    External 1x display to the right: pixel bounds (2880,0,1920,1080),
    appkit_origin=(1440,0), appkit_size=(1920,1080), backing_scale=1.0.

    The second screen's AppKit origin is 1440 (logical width of the Retina),
    NOT 2880 (its pixel x coordinate).  This is the mixed-DPI bug the fix
    addresses: if we used bounds.x=2880 as the AppKit origin, the HUD panel
    would be placed ~1440 points off-screen to the right.
    """

    def setup_method(self):
        # Retina built-in: pixel bounds start at (0,0), 2880×1800 pixels
        # NSScreen.frame → origin=(0,0), size=(1440,900) in AppKit points
        self.retina_screen = _make_screen(
            av_index=0,
            bounds=(0, 0, 2880, 1800),
            is_main=True,
            backing_scale=2.0,
            appkit_origin=(0.0, 0.0),
            appkit_size=(1440.0, 900.0),
        )
        # External 1x: pixel bounds start at (2880,0), 1920×1080 pixels
        # NSScreen.frame → origin=(1440,0), size=(1920,1080) in AppKit points
        self.external_screen = _make_screen(
            av_index=1,
            display_id=2,
            bounds=(2880, 0, 1920, 1080),
            is_main=False,
            backing_scale=1.0,
            appkit_origin=(1440.0, 0.0),
            appkit_size=(1920.0, 1080.0),
        )
        self.region = (100, 100, 800, 600)

    def test_retina_region(self):
        x, y, w, h = transform_region_to_appkit(self.region, self.retina_screen)
        # appkit_x = 0 + 100/2 = 50.0
        # screen AppKit height = 900
        # appkit_y = 0 + (900 - (100+600)/2) = 900 - 350 = 550.0
        # appkit_w = 800/2 = 400.0
        # appkit_h = 600/2 = 300.0
        assert x == 50.0
        assert y == 550.0
        assert w == 400.0
        assert h == 300.0

    def test_external_screen_region_uses_appkit_origin_not_pixel_coord(self):
        """Verify the fix: appkit_origin=1440 is used, not pixel bounds.x=2880."""
        x, y, w, h = transform_region_to_appkit(self.region, self.external_screen)
        # appkit_x = 1440 + 100/1 = 1540.0  (NOT 2880 + 100 = 2980 — the old bug)
        # appkit_y = 0 + (1080 - (100+600)/1) = 1080 - 700 = 380.0
        # appkit_w = 800/1 = 800.0
        # appkit_h = 600/1 = 600.0
        assert x == 1540.0, f"Expected 1540.0 (appkit origin), got {x} (would be 2980.0 with pixel coord)"
        assert y == 380.0
        assert w == 800.0
        assert h == 600.0


class TestComputeFrameStrokeRects:
    """Tests for compute_frame_stroke_rects: 4-strip decomposition."""

    def test_returns_four_strips(self):
        strips = compute_frame_stroke_rects((100.0, 380.0, 800.0, 600.0))
        assert len(strips) == 4

    def test_default_offset_is_4(self):
        """Default offset_pts=4 means each strip is 4 pts wide."""
        top, bottom, left, right = compute_frame_stroke_rects((100.0, 380.0, 800.0, 600.0))
        assert top[3] == 4  # height of top strip
        assert bottom[3] == 4
        assert left[2] == 4  # width of left strip
        assert right[2] == 4

    def test_top_strip_position(self):
        """Top strip sits immediately above the crop rect."""
        top, *_ = compute_frame_stroke_rects((100.0, 380.0, 800.0, 600.0), offset_pts=4)
        x, y, w, h = top
        # Top strip: x-offset=96, y+h=980, w+2*offset=808, height=4
        assert x == 96.0
        assert y == 980.0
        assert w == 808.0
        assert h == 4.0

    def test_bottom_strip_position(self):
        _, bottom, *_ = compute_frame_stroke_rects((100.0, 380.0, 800.0, 600.0), offset_pts=4)
        x, y, w, h = bottom
        assert x == 96.0
        assert y == 376.0  # 380 - 4
        assert w == 808.0
        assert h == 4.0

    def test_left_strip_position(self):
        _, _, left, _ = compute_frame_stroke_rects((100.0, 380.0, 800.0, 600.0), offset_pts=4)
        x, y, w, h = left
        assert x == 96.0   # 100 - 4
        assert y == 376.0  # 380 - 4
        assert w == 4.0
        assert h == 608.0  # 600 + 2*4

    def test_right_strip_position(self):
        *_, right = compute_frame_stroke_rects((100.0, 380.0, 800.0, 600.0), offset_pts=4)
        x, y, w, h = right
        assert x == 900.0  # 100 + 800
        assert y == 376.0
        assert w == 4.0
        assert h == 608.0

    def test_custom_offset(self):
        top, _, left, _ = compute_frame_stroke_rects((0.0, 0.0, 100.0, 50.0), offset_pts=8)
        assert top[3] == 8
        assert left[2] == 8
