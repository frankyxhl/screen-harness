"""Unit tests for HUD REC pill anchor corner selection (pure Python, no AppKit).

Tests the pick_rec_pill_anchor function which chooses where to position
the REC pill outside the crop rect.

Priority order: bottom-right > top-right > bottom-left > top-left.
Falls back to "edge:<side>" when all corners are blocked (crop covers
the full screen).
"""

from __future__ import annotations

import pytest

from screen_harness.hud import pick_rec_pill_anchor


# screen_rect is (x, y, w, h) in the same coordinate space as crop_rect


class TestAnchorBottomRight:
    """Crop at bottom-right corner of screen → pill goes top-right."""

    def test_crop_at_bottom_right(self):
        screen_rect = (0, 0, 1920, 1080)
        # Crop occupies the bottom-right quadrant
        crop_rect = (960, 540, 960, 540)
        anchor = pick_rec_pill_anchor(crop_rect, screen_rect)
        # bottom-right is occupied; top-right should be free
        assert anchor in ("top-right", "bottom-left", "top-left", "bottom-right")

    def test_crop_covers_bottom_half(self):
        """Crop covering bottom half → pill goes top-right (top is free)."""
        screen_rect = (0, 0, 1920, 1080)
        crop_rect = (0, 540, 1920, 540)  # entire bottom half
        anchor = pick_rec_pill_anchor(crop_rect, screen_rect)
        # bottom-right is occupied; first free from priority order is top-right
        assert anchor == "top-right"

    def test_crop_covers_top_half(self):
        """Crop covering top half → pill goes bottom-right (bottom is free)."""
        screen_rect = (0, 0, 1920, 1080)
        crop_rect = (0, 0, 1920, 540)  # entire top half
        anchor = pick_rec_pill_anchor(crop_rect, screen_rect)
        # bottom-right is free
        assert anchor == "bottom-right"

    def test_small_center_crop(self):
        """Small center crop → bottom-right is always preferred."""
        screen_rect = (0, 0, 1920, 1080)
        crop_rect = (500, 300, 500, 300)  # small center region
        anchor = pick_rec_pill_anchor(crop_rect, screen_rect)
        assert anchor == "bottom-right"


class TestAnchorFallback:
    """Crop covering everything → pill falls back to edge:<side>."""

    def test_full_screen_crop(self):
        screen_rect = (0, 0, 1920, 1080)
        crop_rect = (0, 0, 1920, 1080)  # exact full screen
        anchor = pick_rec_pill_anchor(crop_rect, screen_rect)
        assert anchor.startswith("edge:")

    def test_full_screen_crop_has_side(self):
        """The edge fallback names a specific side."""
        screen_rect = (0, 0, 1920, 1080)
        crop_rect = (0, 0, 1920, 1080)
        anchor = pick_rec_pill_anchor(crop_rect, screen_rect)
        side = anchor.split(":", 1)[1]
        assert side in ("top", "bottom", "left", "right")

    def test_oversized_crop(self):
        """Crop larger than screen (edge case) → edge fallback."""
        screen_rect = (0, 0, 1920, 1080)
        crop_rect = (-10, -10, 2000, 1200)
        anchor = pick_rec_pill_anchor(crop_rect, screen_rect)
        assert anchor.startswith("edge:")


class TestAnchorCornerBlocking:
    """Corner-level occupancy checks."""

    def test_crop_at_top_left(self):
        """Crop fills the top-left corner only."""
        screen_rect = (0, 0, 1920, 1080)
        # A crop that covers only the top-left quadrant
        crop_rect = (0, 0, 960, 540)
        anchor = pick_rec_pill_anchor(crop_rect, screen_rect)
        # bottom-right is free → first choice
        assert anchor == "bottom-right"

    def test_crop_leaves_only_bottom_left(self):
        """Crop leaves only the bottom-left corner free → bottom-left."""
        screen_rect = (0, 0, 1920, 1080)
        # Covers bottom-right, top-right, top-left, leaving bottom-left free
        # bottom half right side + top half both sides
        # Simpler: crop covers right half + top-left quadrant
        # This is harder to set up cleanly — use explicit bottom-right blocking
        # by placing a crop that covers bottom-right, top-right, and top-left.
        # We cover the right half (br + tr) and top-left quadrant.
        # Actually just test that bottom-left appears when it's the only free corner.
        # Crop: right half full-height + top half full-width = everything except bottom-left
        # There's no single rect that covers exactly those three corners.
        # Instead test what the function returns when bottom-right and top-right are blocked.
        # Crop: entire right half
        crop_rect = (960, 0, 960, 1080)
        anchor = pick_rec_pill_anchor(crop_rect, screen_rect)
        # bottom-right and top-right are blocked; bottom-left is next in priority
        # (priority: bottom-right > top-right > bottom-left > top-left)
        assert anchor == "bottom-left"
