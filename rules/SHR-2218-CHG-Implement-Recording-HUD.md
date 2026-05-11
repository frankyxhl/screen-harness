# CHG-2218: Implement Recording HUD Overlay (D2)

**Applies to:** SHR project
**Last updated:** 2026-05-11
**Last reviewed:** 2026-05-11
**Status:** Proposed
**Date:** 2026-05-11
**Requested by:** Frank Xu (D2 in SHR-2212)
**Priority:** High
**Change Type:** Normal
**Targets:** src/screen_harness/hud.py (new), src/screen_harness/helpers.py, src/screen_harness/run.py, src/screen_harness/recorder.py (tests only), tests/
**Implements:** SHR-2214 PRP (Approved R2, 3/3 trinity PASS)
**Carries follow-up:** CHG-2217 §Plan item 6 — paired coloured-square AV↔CGDirectDisplayID binding invariant test (deferred from D1 with the explicit commitment "hard gate before any HUD code merges").

---

## What

Implement PRP-2214 R2 verbatim. Concrete deliverables:

1. **New module `src/screen_harness/hud.py`**:
   - `RecPillPanel` (NSPanel subclass): red rounded "● REC HH:MM:SS" pill,
     auto-positioned at the nearest safe edge *outside* the crop rect (bottom-
     right > top-right > bottom-left > top-left; falls back to the screen
     edge closest to crop).
   - `RegionFramePanel`: four thin opaque NSPanels arranged as a stroke
     4 px outside the crop rect (top + bottom + left + right). Avoids the
     transparent-panel-with-frame coordinate-system traps reviewers warned
     about.
   - Both panels configured:
     - `level = NSStatusWindowLevel`.
     - `ignoresMouseEvents = True` (click-through).
     - `opaque = True` (no transparency math).
     - `collectionBehavior |= CanJoinAllSpaces | Stationary | FullScreenAuxiliary`.
   - 1-second `NSTimer` updates REC pill text.

2. **Coordinate transform** (load-bearing, was missing from R1):
   - `region = (rx, ry, rw, rh)` is picked-screen pixels, top-left origin
     (matches `crop=W:H:X:Y` ffmpeg filter).
   - `NSPanel.setFrame_display_` is AppKit points, bottom-left origin, on
     the global AppKit coordinate space (where each screen has a positioned
     frame).
   - Conversion (using `ScreenDevice.backing_scale` from D1):
     ```
     appkit_x = screen.frame.origin.x + region_x / backing_scale
     appkit_y = screen.frame.origin.y
                + (screen.frame.height - (region_y + region_h) / backing_scale)
     ```
   - Golden-fixture unit tests cover: 1× 1080p main, 2× 2880×1800 @2x
     Retina main, side-by-side 1080p + Retina dual screen.

3. **HUD subprocess model** (avoids AppKit run-loop sharing with FFmpeg):
   - Parent → child via JSON-on-stdin: `{"cmd": "start", "screen": {...},
     "region": [rx, ry, rw, rh], "started_at": <unix-ts>}` then
     `{"cmd": "stop"}`.
   - Child runs `NSApp.run()` on its main thread.
   - **Parent-death watcher** = stdin EOF → child calls `NSApp.terminate_`.
     Canonical Unix idiom (replaces R1's incorrect NOTE_EXIT spec). No
     entitlements needed.
   - Child is launched via `python -m screen_harness.hud` from `start_recording`.

4. **`helpers.start_recording` integration**:
   - New kwarg `hud: bool = True`.
   - HUD activates only when `region=` is set AND it leaves visible screen
     real estate outside the crop. Otherwise: log a single warning line
     ("Full-screen recording — HUD disabled; pass region= to enable") and
     proceed without HUD.
   - On HUD launch failure (subprocess won't start, PyObjC absent, etc.):
     log warning, proceed without HUD — recording must NOT fail because the
     HUD failed.
   - `stop_recording` closes the HUD subprocess stdin (→ child sees EOF →
     terminates within 200ms). Cleanup runs on every path including
     KeyboardInterrupt.

5. **CHG-2217 follow-up — paired coloured-square invariant test**:
   - New `tests/test_screens_invariant.py::test_av_to_display_binding_via_coloured_square`
     (macOS-gated, gated on PyObjC + FFmpeg availability):
     1. For each `ScreenDevice` returned by `probe_screens()`:
        a. Draw a known-colour AppKit window (e.g. fully red `#FF0000`) on
           the matched `NSScreen` via `display_id`.
        b. Record a 0.3 s clip of *only that device* using
           `build_screen_record_command(screen_device=d, ...)`.
        c. Sample the centre pixel of a middle frame.
        d. Assert the pixel matches the expected colour within tolerance.
     2. Each screen gets a unique colour so cross-binding bugs (screen A
        gets device B's index) fail loudly.
     - Skip cleanly if PyObjC absent, FFmpeg lacks avfoundation, or
       running headless.

6. **HUD negative-space selftest** (hard contract from PRP §Tests):
   - `tests/test_hud_selftest.py::test_hud_pixels_never_inside_crop_region`
     (macOS-gated):
     1. Start a recording with `region=(100,100,800,600)` and `hud=True`.
     2. Record 3 s.
     3. Stop. Crop the recorded frames to the region.
     4. Assert no red HUD pixels appear inside the crop rect.
   - If the assertion fails, the implementation has a coordinate bug or the
     HUD bled inside; either way the PR is blocked.

7. **Tests** (non-macOS unit):
   - `tests/test_hud_coords.py`: golden-fixture coordinate transform for
     Retina, dual-screen, region-at-screen-edges.
   - `tests/test_hud_protocol.py`: JSON command parser + state machine (no
     AppKit needed).
   - `tests/test_hud_anchor.py`: REC pill anchor-corner choice for various
     crop rects vs screen bounds.

## Why

D2 in SHR-2212. User needs (a) a visible "recording in progress" signal and
(b) a visible frame around the capture region. Burning either into the
captured frames is unacceptable. SHR-2216 spike + 3-reviewer convergence
established that `NSWindowSharingNone` is unreliable for FFmpeg avfoundation
capture, so the HUD must live outside the crop rect.

## Impact

- New module `src/screen_harness/hud.py` (~250 lines expected).
- New optional CLI entry `python -m screen_harness.hud` (subprocess only).
- `helpers.start_recording` gains `hud=True` kwarg (default on).
- `helpers.stop_recording` gains cleanup branch.
- No breaking changes to existing recorder/helpers contracts; HUD is opt-out.
- Full-screen recording (`region=None` or region covers screen) prints a
  warning but does not fail.

## Plan

Follow COR-1500 TDD overlay: RED → GREEN → REFACTOR.

1. **RED**: pure-Python coord transform tests (`test_hud_coords.py`),
   anchor-corner tests (`test_hud_anchor.py`), JSON protocol tests
   (`test_hud_protocol.py`).
2. **GREEN**: implement `hud.py` Python surfaces (no AppKit yet — extract
   pure functions for transform, anchor pick, protocol state machine; then
   thin AppKit wrappers around them).
3. **RED**: paired coloured-square invariant test (CHG-2217 §Plan item 6)
   in `test_screens_invariant.py`. Skip if any prerequisite missing.
4. **GREEN**: implement the test using `Quartz.CGDisplayCreateImage` to
   verify FFmpeg captured the correct display.
5. **RED**: HUD negative-space selftest (`test_hud_selftest.py`).
6. **GREEN**: wire HUD subprocess into `helpers.start_recording` /
   `stop_recording`.
7. **REFACTOR**: tighten error paths; ensure recording never aborts because
   HUD failed; add a stdout line on HUD activation/skip so users can see
   what happened.
8. Run `uv run pytest -q` — all tests green. macOS-gated tests run with
   PyObjC dev extra; skip cleanly on Linux CI.
9. Run `uv run python -m compileall -q src tests` — 0 errors.
10. Run `uvx --from fx-alfred af validate` — 0 issues.
11. Update README + SKILL.md `start_recording` helper API table with
    `hud=` kwarg.

## Rollback

Revert this branch's commits on `main`. The new module, CLI entry, and
HUD-related kwargs are isolated — removing them leaves prior recorder /
helper behavior intact. The coloured-square invariant test promotion from
CHG-2217 stays committed as a free-standing regression net.

## Tests Gate (CI must pass)

- All existing tests still pass (165 → 165+ baseline).
- New unit tests for coord transform, anchor pick, JSON protocol all green.
- Compileall clean.
- `af validate` 0 issues.
- macOS-gated tests skip cleanly on Linux; pass on local Mac dev run
  (manual verification before requesting review).

## Approval

- [ ] Approved by: <reviewer> on <date>

---

## Change History

| Date | Change | By |
|------|--------|----|
| 2026-05-11 | Initial CHG, implements approved PRP-2214 R2; absorbs the paired coloured-square AV↔CGDirectDisplayID test deferred from CHG-2217 §Plan item 6. | Claude Code |
