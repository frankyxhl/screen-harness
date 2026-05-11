# CHG-2218: Implement Recording HUD Overlay (D2)

**Applies to:** SHR project
**Last updated:** 2026-05-11
**Last reviewed:** 2026-05-11
**Status:** Completed
**Merged:** PR #7 (commit 9163013252) on 2026-05-11; closed Codex bot findings across 11 review rounds (2× P1 + 9× P2) + trinity final 3/3 PASS (glm/deepseek/minimax). HUD production rendering verified by manual smoke test on user's interactive terminal session.
**Revision:** R2 — addresses Trinity R1 review (GLM FAIL 8.4, DeepSeek FAIL 6.3, MiniMax FAIL 5.8)
**Approved by:** Trinity R2 — glm PASS 9.2, deepseek PASS 9.2, minimax PASS 9.2 (3/3 unanimous, all R1 blockers closed, zero new blockers)
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
   - `RecPillPanel` (NSPanel subclass): rounded pill with fill
     **`#FF3B30`** (Apple system red, pinned so the negative-space selftest
     can grep for it without false positives from arbitrary on-screen red
     UI). Text "● REC HH:MM:SS" in white, SF Mono 14pt. Auto-positioned at
     the nearest safe edge *outside* the crop rect (priority: bottom-right
     > top-right > bottom-left > top-left; if no corner has room, anchor to
     the screen edge closest to the crop).
   - `RegionFramePanel`: four thin opaque NSPanels arranged as a stroke
     **4 AppKit points** wide (NOT pixels — explicit since on a Retina
     backing_scale=2 display the visual width otherwise doubles), outside
     the crop rect (top + bottom + left + right). Same `#FF3B30` fill.
     Avoids the transparent-panel-with-frame coordinate-system traps
     reviewers warned about.
   - Both panels configured:
     - `level = NSStatusWindowLevel`.
     - `ignoresMouseEvents = True` (click-through).
     - `opaque = True` (no transparency math).
     - `collectionBehavior |= CanJoinAllSpaces | Stationary | FullScreenAuxiliary`.
   - 1-second `NSTimer` updates REC pill text. **Timer derives elapsed
     from `int(time.monotonic() - started_at)` each tick** (not from a
     tick counter) to avoid drift over multi-minute recordings.

   **Pure-function extraction targets** (RED-tested before AppKit
   wrappers — MiniMax B3, scope item):
   - `transform_region_to_appkit(region, screen) -> (x, y, w, h)`
   - `pick_rec_pill_anchor(crop_rect, screen_rect) -> Anchor`
   - `compute_frame_stroke_rects(crop_rect, *, offset_pts: int = 4) -> [TopRect, BottomRect, LeftRect, RightRect]`
   - `format_rec_time(elapsed_seconds: int) -> "HH:MM:SS"`
   - `parse_command(line: str) -> dict` + `HUDState` state machine

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
   - **Launched via `sys.executable -m screen_harness.hud`** — never bare
     `python`. Under uv venvs the parent's interpreter is what has the
     package installed (DeepSeek B5).
   - Parent → child via JSON-on-stdin: `{"cmd": "start", "screen": {...},
     "region": [rx, ry, rw, rh], "started_at": <monotonic-seconds>}` then
     `{"cmd": "stop"}`.
   - **`started_at` is the FFmpeg-confirmed-running moment** (after the
     parent reads the first ffmpeg stderr line indicating capture began),
     not `subprocess.Popen` time. Otherwise the displayed timer leads the
     recorded duration by 200–500 ms (DeepSeek B6).
   - Child runs `NSApp.run()` on its main thread.
   - **Parent-death watcher** = a stdin-reader background thread inside
     the child. On EOF (parent closed stdin or died) the thread schedules
     shutdown on the AppKit main thread via
     `PyObjCTools.AppHelper.callAfter(NSApp.terminate_, None)`. Calling
     `NSApp.terminate_` from a background thread is undefined behaviour;
     `callAfter` enqueues onto the main run loop (DeepSeek B1).
   - Child is launched via `sys.executable -m screen_harness.hud` from
     `start_recording`.

4. **`helpers.start_recording` integration**:
   - New kwarg `hud: bool = True`.
   - HUD activates only when `region=` is set AND it leaves visible screen
     real estate outside the crop. Otherwise: log a single warning line
     ("Full-screen recording — HUD disabled; pass region= to enable") and
     proceed without HUD.
   - **Region overflow validation**: if `rx+rw > screen.bounds.w` or
     `ry+rh > screen.bounds.h`, raise `ValueError` with diagnostic (named
     `RegionOutOfBoundsError` for catchability) — never silently clamp
     (MiniMax B4).
   - **Multi-monitor mismatch**: if `region` is interpreted in the picked
     screen's pixel coordinates but `region` extends past that screen, the
     HUD has no coherent placement. Refuse with a clear error pointing the
     user at `screen-harness probe-screens` (MiniMax A3).
   - On HUD launch failure (subprocess won't start, PyObjC absent, etc.):
     log warning, proceed without HUD — recording must NOT fail because the
     HUD failed. `metadata.json` gains `hud_active: bool` field so
     post-hoc debugging can see whether the HUD ran (MiniMax A2).
   - `stop_recording` closes the HUD subprocess stdin (→ child sees EOF →
     terminates within 200ms). Cleanup runs on every path: normal stop,
     FFmpeg crash, KeyboardInterrupt, parent SIGKILL. Use
     `try/finally` + `atexit` for KeyboardInterrupt safety.

5. **CHG-2217 follow-up — paired coloured-square invariant test**:
   - New `tests/test_screens_invariant.py::test_av_to_display_binding_via_coloured_square`
     (macOS-gated, gated on PyObjC + FFmpeg availability):
     1. **Per-screen colour allocation** (max 3 displays expected):
        - display 0 → `#FF0000` (pure red)
        - display 1 → `#00FF00` (pure green)
        - display 2 → `#0000FF` (pure blue)
        These are maximally separated in RGB space so a cross-bound screen
        produces a colour at L*a*b* distance > 80 from expected — well
        outside any tolerance.
     2. For each `ScreenDevice` returned by `probe_screens()`:
        a. Draw a borderless full-screen `NSWindow` filled with the assigned
           colour on the matched `NSScreen` via `display_id`.
        b. Record a 0.5 s clip of *only that device* (longer than 0.3 s
           to let FFmpeg's avfoundation startup settle) using
           `build_screen_record_command(screen_device=d, ...)`.
        c. Sample an **8×8 centre block** of the middle frame (single
           pixel is too noisy with H.264 chroma subsampling).
        d. Compute mean RGB; assert **Euclidean distance ≤ 10** from
           expected (e.g. for red `(255, 0, 0)`, any sample with
           `√((R-255)² + G² + B²) ≤ 10` passes).
     3. **Skip semantics**: if `len(probe_screens()) < 1`, PyObjC absent,
        FFmpeg lacks avfoundation, or the host appears headless (no
        WindowServer), skip with a clear reason.

   **Test independence from production code**: the AppKit draw uses
   `display_id` (Quartz API path), the FFmpeg capture uses `av_index`
   (ffmpeg-avfoundation enumeration). They are independent enumeration
   orders — the test verifies the *binding* probe_screens computes
   between them, not a tautology (DeepSeek pressure-test #7).

6. **HUD negative-space selftest** (hard contract from PRP §Tests):
   - `tests/test_hud_selftest.py::test_hud_pixels_never_inside_crop_region`
     (macOS-gated):
     1. Start a recording with `region=(100,100,800,600)` and `hud=True`.
     2. Record 3 s.
     3. Stop. For 5 evenly-spaced frames across the clip, crop to the
        region and scan every pixel.
     4. **HUD-colour predicate** (pinned to the `#FF3B30` REC pill /
        frame fill, which is distinct from common UI reds like `#FF0000`):
        a pixel is "HUD red" iff `230 ≤ R ≤ 255 AND 40 ≤ G ≤ 80
        AND 30 ≤ B ≤ 70`. This box is chosen to be tight around
        `(255, 59, 48)` with H.264 chroma-subsampling tolerance ≈ ±20 per
        channel, while excluding pure-red UI elements (G=0).
     5. Assert `hud_red_count == 0` for every scanned frame.
   - If the assertion fails, the implementation has a coordinate bug or
     the HUD bled inside; either way the PR is blocked.

7. **HUD lifecycle latency tests** (PRP §Scope, dropped from R1 — GLM B1,
   DeepSeek B3):
   - `tests/test_hud_lifecycle.py::test_clean_start_stop_under_200ms`
     (macOS-gated): spawn subprocess, send `start` then `stop`, assert
     full teardown latency ≤ 200 ms.
   - `tests/test_hud_lifecycle.py::test_startup_under_300ms`
     (macOS-gated): spawn subprocess, send `start`, assert HUD window
     visible (`NSApp.windows().count() > 0` over IPC) ≤ 300 ms.
   - `tests/test_hud_lifecycle.py::test_parent_crash_child_exits_under_1s`
     (macOS-gated): spawn HUD as a child of an intermediate parent,
     SIGKILL the intermediate parent, assert HUD subprocess exits ≤ 1 s
     via stdin EOF detection.

8. **HUD-on vs HUD-off frame-hash equivalence** (PRP §Tests BDD, dropped
   from R1 — GLM B2, DeepSeek B4):
   - `tests/test_hud_selftest.py::test_hud_on_vs_off_frame_hashes_match_outside_bands`
     (macOS-gated): record the same scene twice with identical region,
     once `hud=True` and once `hud=False`. For each of 5 sampled middle
     frames, crop to the region rect, compute per-frame SHA-256 over the
     cropped pixels, assert hashes match between the two runs. This
     catches anti-aliasing / compositing leaks that the negative-space
     selftest would miss (a single sub-pixel pink leak would not be
     "HUD red" by colour predicate but would change the hash).

9. **HUD-failure-recovery test** (GLM A3, advisory promoted):
   - `tests/test_helpers_hud.py::test_recording_proceeds_when_hud_launch_fails`:
     mock `subprocess.Popen` for the HUD path to raise; assert
     `start_recording` completes, `metadata.json` has `hud_active: false`,
     and the recording itself proceeds normally.

10. **Tests** (non-macOS unit):
    - `tests/test_hud_coords.py`: golden-fixture coordinate transform for
      Retina, dual-screen, region-at-screen-edges. Also tests
      `compute_frame_stroke_rects` for the 4-strip decomposition + offset.
    - `tests/test_hud_protocol.py`: JSON command parser + state machine
      (no AppKit needed). Includes `format_rec_time` golden cases.
    - `tests/test_hud_anchor.py`: REC pill anchor-corner choice for
      various crop rects vs screen bounds.
    - `tests/test_hud_region_validation.py`: `RegionOutOfBoundsError`
      raised for overflow; multi-monitor mismatch raises with helpful
      message.

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

1. **RED**: pure-Python tests
   - `test_hud_coords.py` — `transform_region_to_appkit` golden fixtures.
   - `test_hud_coords.py` — `compute_frame_stroke_rects` 4-strip
     decomposition + offset.
   - `test_hud_anchor.py` — `pick_rec_pill_anchor` priority cases.
   - `test_hud_protocol.py` — `parse_command`, `HUDState`,
     `format_rec_time`.
   - `test_hud_region_validation.py` — `RegionOutOfBoundsError`,
     multi-monitor mismatch refusal.
2. **GREEN — pure-Python core**: implement each pure function in
   `hud.py` *without* AppKit imports at top level. The AppKit subclasses
   are placed later in the same module behind a lazy import so unit
   tests don't trigger Cocoa initialisation.
3. **GREEN — AppKit wrappers**: `RecPillPanel`, `RegionFramePanel`
   factories, `run_hud_subprocess`. Use the pure functions for all
   geometric work. Verify the panel actually appears via a manual smoke
   test (document the command in the PR body).
4. **RED**: paired coloured-square invariant test
   (`test_screens_invariant.py::test_av_to_display_binding_via_coloured_square`).
5. **GREEN**: implement it using AppKit draws (ground truth) +
   FFmpeg captures via `build_screen_record_command(screen_device=d)`
   (verification). The two paths use independent enumerations so the
   binding is genuinely tested.
6. **RED**: HUD negative-space selftest + lifecycle latency tests +
   frame-hash equivalence + HUD-failure-recovery.
7. **GREEN**: wire HUD subprocess into `helpers.start_recording` /
   `stop_recording`. Use `sys.executable -m screen_harness.hud`.
   Synchronise `started_at` to FFmpeg's confirmed-running moment.
8. **REFACTOR**: tighten error paths; ensure recording never aborts
   because HUD failed; add a stdout line on HUD activation/skip; ensure
   teardown runs from `try/finally` + `atexit` so KeyboardInterrupt
   doesn't orphan the subprocess.
9. Run `uv run pytest -q` — all tests green. macOS-gated tests run with
   PyObjC dev extra; skip cleanly on Linux CI.
10. Run `uv run python -m compileall -q src tests` — 0 errors.
11. Run `uvx --from fx-alfred af validate` — 0 issues.
12. Update README + SKILL.md `start_recording` helper API table with
    `hud=` kwarg + full-screen-disabled note.

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
| 2026-05-11 | R2 — Address Trinity R1 (GLM 8.4, DeepSeek 6.3, MiniMax 5.8, all FAIL): pin REC red to `#FF3B30` + tight colour predicate; spec 4-pt stroke unit (not pixels); add lifecycle latency tests (200ms teardown / 300ms startup / 1s parent-crash); add HUD-on-vs-off frame-hash equivalence test; add HUD-failure-recovery test; spec `sys.executable` + `AppHelper.callAfter` thread bridge + FFmpeg-confirmed `started_at` origin + monotonic-clock timer derivation; spec `compute_frame_stroke_rects` + `format_rec_time` pure-function extractions; spec `RegionOutOfBoundsError` overflow + multi-monitor mismatch refusal; spec `metadata.json["hud_active"]`; per-screen colour allocation + 8×8 centre block + Euclidean ≤10 for coloured-square test. | Claude Code |
| 2026-05-11 | Approved R2 — Trinity 3/3 PASS @ 9.2; implementation via coder (sonnet) subagent. | Claude Code |
| 2026-05-11 | Codex bot review loop (11 rounds, COR-1612 + COR-1615): P1 r3 `setActivationPolicy_(4)`→1 (root cause behind SHR-2216 misattribution); P1 r5 edge-fallback pill leaked into crop → fail-closed "none" sentinel; P2 r1 anchor needs room for full pill; P2 r2 popen-time on timeout + HUD survival poll; P2 r4 _STATE populated before wait; P2 r6 cleanup on RecordingStartFailed; P2 r7 start/status race via sync state update; P2 r8 mixed-DPI coords via NSScreen.frame origin; P2 r9 abort tears down HUD; P2 r10 track HUD before metadata write; P2 r11 select.select timeout on readline. | Claude Code |
| 2026-05-11 | Trinity final 3/3 PASS: glm 9.0 (after B1 fix) / deepseek 9.25 / minimax 9.35. HUD production rendering verified by manual smoke test from user's interactive terminal. Merged PR #7 = 9163013252. | Claude Code |
| 2026-05-11 | Status → Completed after PR #7 merge. | Claude Code |
