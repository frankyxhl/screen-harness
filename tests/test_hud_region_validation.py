"""Unit tests for HUD region validation (pure Python, no AppKit).

Tests RegionOutOfBoundsError for overflow cases and multi-monitor mismatch
refusal from validate_region_for_screen().
"""

from __future__ import annotations

import pytest

from screen_harness.hud import RegionOutOfBoundsError, validate_region_for_screen
from screen_harness.screens import ScreenDevice


def _make_screen(
    *,
    bounds: tuple[int, int, int, int],
    backing_scale: float = 1.0,
    av_index: int = 0,
) -> ScreenDevice:
    return ScreenDevice(
        av_index=av_index,
        av_name="Capture screen 0",
        display_id=1,
        bounds=bounds,
        is_main=True,
        backing_scale=backing_scale,
    )


class TestRegionOutOfBoundsError:
    """RegionOutOfBoundsError is a ValueError subclass."""

    def test_is_value_error(self):
        assert issubclass(RegionOutOfBoundsError, ValueError)


class TestValidateRegionOverflow:
    """validate_region_for_screen raises RegionOutOfBoundsError on overflow."""

    def setup_method(self):
        self.screen = _make_screen(bounds=(0, 0, 1920, 1080))

    def test_valid_region_does_not_raise(self):
        validate_region_for_screen((100, 100, 800, 600), self.screen)

    def test_region_exactly_at_boundary_does_not_raise(self):
        validate_region_for_screen((0, 0, 1920, 1080), self.screen)

    def test_x_plus_w_overflow_raises(self):
        with pytest.raises(RegionOutOfBoundsError):
            validate_region_for_screen((200, 0, 1800, 100), self.screen)
            # 200 + 1800 = 2000 > 1920

    def test_y_plus_h_overflow_raises(self):
        with pytest.raises(RegionOutOfBoundsError):
            validate_region_for_screen((0, 200, 100, 1000), self.screen)
            # 200 + 1000 = 1200 > 1080

    def test_error_message_contains_diagnostic(self):
        with pytest.raises(RegionOutOfBoundsError, match="1920"):
            validate_region_for_screen((200, 0, 1800, 100), self.screen)

    def test_error_message_mentions_probe_screens(self):
        with pytest.raises(RegionOutOfBoundsError, match="probe-screens"):
            validate_region_for_screen((200, 0, 1800, 100), self.screen)


class TestValidateRegionMultiMonitorMismatch:
    """validate_region_for_screen raises when region extends beyond screen."""

    def test_region_starts_outside_screen_width_raises(self):
        screen = _make_screen(bounds=(0, 0, 1920, 1080))
        # Region starts well past screen right edge
        with pytest.raises(RegionOutOfBoundsError):
            validate_region_for_screen((1950, 0, 100, 100), screen)
            # 1950 > 1920 (screen width)

    def test_region_starts_outside_screen_height_raises(self):
        screen = _make_screen(bounds=(0, 0, 1920, 1080))
        with pytest.raises(RegionOutOfBoundsError):
            validate_region_for_screen((0, 1100, 100, 100), screen)
            # 1100 + 100 = 1200 > 1080

    def test_offset_screen_bounds_respected(self):
        """Screen with non-zero bounds origin: region is in picked-screen-local coords."""
        screen = _make_screen(bounds=(1920, 0, 1920, 1080))
        # Region is local to screen so (0, 0, 800, 600) is valid
        validate_region_for_screen((0, 0, 800, 600), screen)

    def test_offset_screen_overflow_raises(self):
        screen = _make_screen(bounds=(1920, 0, 1920, 1080))
        with pytest.raises(RegionOutOfBoundsError):
            validate_region_for_screen((0, 0, 2000, 600), screen)
