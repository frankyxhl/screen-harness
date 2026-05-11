"""Unit tests for HUD REC pill anchor corner selection (pure Python, no AppKit).

`pick_rec_pill_anchor` operates in AppKit point space (bottom-left origin,
y increases upward).  A placement is accepted only when the *full* pill
rect (160×36 + 12pt margin from the crop, by default) fits entirely
inside the screen rect.

Priority order (Codex P2 round on PR #7 expanded the 4-corner set to 8):
    side placements first:    bottom-right > top-right > bottom-left > top-left
    then stacked placements:  above-right > below-right > above-left > below-left
    finally:                  edge:<side>
"""

from __future__ import annotations

import pytest

from screen_harness.hud import pick_rec_pill_anchor, pill_placement


SCREEN = (0, 0, 1920, 1080)  # AppKit: x=0..1920, y=0..1080 (y up)


# ---------------------------------------------------------------------------
# Side placements (4 corners): preferred when crop leaves lateral room
# ---------------------------------------------------------------------------

class TestSidePlacements:
    def test_small_centre_crop_picks_bottom_right(self):
        """A small centre crop has room on every side — bottom-right wins by priority."""
        crop = (500, 300, 500, 300)  # 500×300 in the middle
        assert pick_rec_pill_anchor(crop, SCREEN) == "bottom-right"

    def test_crop_in_appkit_bottom_left_quadrant_picks_bottom_right(self):
        """Crop at AppKit (0,0,960,540) = bottom-left quadrant → bottom-right of crop has room."""
        crop = (0, 0, 960, 540)
        # bottom-right placement: (cx+cw+margin, cy-pill_h-margin) = (972, -48). py < 0 NO
        # top-right placement: (972, 552). 972+160=1132 ≤ 1920 OK, 552+36=588 ≤ 1080 OK. fits.
        assert pick_rec_pill_anchor(crop, SCREEN) == "top-right"

    def test_crop_in_appkit_top_right_quadrant_picks_bottom_left(self):
        """Crop at AppKit (960,540,960,540) = top-right quadrant → bottom-left of crop has room."""
        crop = (960, 540, 960, 540)
        # bottom-right: (1932, 492) - px+pw=2092 > 1920 NO
        # top-right:    (1932, 1092) NO
        # bottom-left:  (788, 492). 788 ≥ 0 OK, 492+36=528 ≤ 1080 OK. fits.
        assert pick_rec_pill_anchor(crop, SCREEN) == "bottom-left"


# ---------------------------------------------------------------------------
# Stacked placements (above / below): used when full-width / full-height crops
# leave only vertical / horizontal strips of free space.  Codex P2 case.
# ---------------------------------------------------------------------------

class TestStackedPlacements:
    def test_full_width_crop_top_half_appkit_picks_below_right(self):
        """AppKit crop (0,540,1920,540) covers the top half of the screen.
        No lateral room (crop spans full width).  Pill must go BELOW the
        crop, in the free bottom half."""
        crop = (0, 540, 1920, 540)
        assert pick_rec_pill_anchor(crop, SCREEN) == "below-right"

    def test_full_width_crop_bottom_half_appkit_picks_above_right(self):
        """AppKit crop (0,0,1920,540) covers the bottom half.  Pill must
        go ABOVE the crop, in the free top half."""
        crop = (0, 0, 1920, 540)
        assert pick_rec_pill_anchor(crop, SCREEN) == "above-right"

    def test_codex_p2_tight_crop(self):
        """Codex bot P2 (PR #7): crop (0,0,1900,1000) leaves only 20pt to the
        right and 80pt above — bottom-right anchor's pill would overflow the
        screen.  Function must reject bottom-right and pick a placement
        where the pill actually fits."""
        crop = (0, 0, 1900, 1000)
        anchor = pick_rec_pill_anchor(crop, SCREEN)
        assert anchor != "bottom-right"
        # The 80-tall strip above the crop is 1900 wide — fits a 160×36 pill.
        # "above-right" places pill at (cx+cw-pill_w, cy+ch+margin) = (1740, 1012).
        # 1740+160=1900 ≤ 1920 OK; 1012+36=1048 ≤ 1080 OK.
        assert anchor == "above-right"
        # Verify with pill_placement directly
        px, py = pill_placement(anchor, crop)
        assert 0 <= px and px + 160 <= 1920
        assert 0 <= py and py + 36 <= 1080


# ---------------------------------------------------------------------------
# None sentinel: returned when NO 8-position placement fits (fail-closed)
# ---------------------------------------------------------------------------

class TestNoneAnchor:
    def test_tight_crop_returns_none_anchor(self):
        """crop=(10,10,1900,1060) on 1920×1080 — all 8 placements overflow → 'none'."""
        crop = (10, 10, 1900, 1060)
        assert pick_rec_pill_anchor(crop, SCREEN) == "none"

    def test_full_screen_crop_returns_none_anchor(self):
        """Exact full-screen crop → 'none' (replaces old edge: expectation)."""
        crop = (0, 0, 1920, 1080)
        assert pick_rec_pill_anchor(crop, SCREEN) == "none"

    def test_oversized_crop_returns_none_anchor(self):
        """Crop larger than screen → all 8 placements overflow → 'none'."""
        crop = (-10, -10, 2000, 1200)
        assert pick_rec_pill_anchor(crop, SCREEN) == "none"

    def test_none_anchor_rejected_by_pill_placement(self):
        """pill_placement('none', …) raises ValueError — same as any unknown anchor."""
        with pytest.raises(ValueError, match="Unknown anchor"):
            pill_placement("none", (0, 0, 100, 100))


# ---------------------------------------------------------------------------
# Configurable pill dimensions
# ---------------------------------------------------------------------------

class TestPillDimsKwarg:
    def test_smaller_pill_fits_in_tight_strip(self):
        """A 40×20 pill should fit in a 60pt right strip even when 160×36 doesn't."""
        crop = (0, 0, 1820, 1000)  # 100pt to right, 80pt above
        # Default 160-wide pill: bottom-right placement px+pw = 1992 > 1920 NO; should fall to above
        anchor_default = pick_rec_pill_anchor(crop, SCREEN)
        assert anchor_default != "bottom-right"

        # 40-wide pill: bottom-right placement (1820+12, 0-20-12) = (1832, -32). py<0 NO
        # top-right: (1832, 1012). 1832+40=1872 ≤ 1920 OK; 1012+20=1032 ≤ 1080 OK. fits.
        anchor_small = pick_rec_pill_anchor(crop, SCREEN, pill_w=40, pill_h=20, margin=12)
        assert anchor_small == "top-right"


# ---------------------------------------------------------------------------
# pill_placement (returns concrete (px, py) AppKit coords)
# ---------------------------------------------------------------------------

class TestPillPlacement:
    def test_above_right_places_pill_right_aligned_above_crop(self):
        crop = (100, 100, 800, 600)
        px, py = pill_placement("above-right", crop)
        # px = cx + cw - pill_w = 100 + 800 - 160 = 740
        # py = cy + ch + margin = 100 + 600 + 12 = 712
        assert (px, py) == (740, 712)

    def test_below_left_places_pill_left_aligned_below_crop(self):
        crop = (100, 100, 800, 600)
        px, py = pill_placement("below-left", crop)
        # px = cx = 100
        # py = cy - pill_h - margin = 100 - 36 - 12 = 52
        assert (px, py) == (100, 52)

    def test_unknown_anchor_raises(self):
        with pytest.raises(ValueError, match="Unknown anchor"):
            pill_placement("nonsense", (0, 0, 100, 100))
