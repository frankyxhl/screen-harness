# CHG-2217: Implement Smart Screen Selection (D1)

**Applies to:** SHR project
**Last updated:** 2026-05-11
**Last reviewed:** 2026-05-11
**Status:** Proposed
**Date:** 2026-05-11
**Requested by:** Frank Xu (D1 in SHR-2212)
**Priority:** High
**Change Type:** Normal
**Targets:** src/screen_harness/screens.py (new), src/screen_harness/admin.py, src/screen_harness/helpers.py, src/screen_harness/recorder.py, src/screen_harness/run.py, src/screen_harness/metadata.py, tests/
**Implements:** SHR-2213 PRP (Approved, 3/3 trinity PASS)

---

## What

Implement PRP-2213 R2 verbatim. Concrete deliverables:

1. New module `src/screen_harness/screens.py`:
   - `ScreenDevice` + `PickedScreen` dataclasses.
   - `probe_screens(*, ffmpeg=...) -> list[ScreenDevice]` — wraps
     `admin.list_avfoundation_devices`, computes `camera_count =
     N_video_devices − N_active_displays` via Quartz, binds k-th screen
     device to k-th `CGDirectDisplayID`.
   - `resolve_screen(spec, *, app=None, ffmpeg=...) -> PickedScreen`
     handling all spec/app cases from PRP §Scope table.
   - `ScreenProbeError` exception.
   - Lazy PyObjC import with degrade-to-main-display fallback.

2. New CLI subcommand: `screen-harness probe-screens [--json]`
   (wired in `run.py`).

3. `helpers.start_recording` integration:
   - Add kwarg `app: str | None = None`.
   - Always call `probe_screens()`; print inventory to stdout once per
     process (cache in `_STATE`).
   - Call `resolve_screen(screen, app=app)`; pass `picked.device.av_index`
     to `build_screen_record_command`.
   - Write `picked_screen` block into `metadata.json`.

4. `recorder.build_screen_record_command` accepts a `ScreenDevice`
   (or raises if invoked with a raw int that fails screen-device
   validation).

5. `admin.build_doctor_summary` adds `picked-screen-default:` line via
   `resolve_screen(None)`.

6. Tests:
   - `tests/fixtures/avfoundation_devices/{en,zh,ja,es,fr}.txt` —
     real-world device listing fixtures.
   - `tests/test_screens.py` — `probe_screens` parses each fixture
     locale-independently; `resolve_screen` spec×app matrix; JSON-schema
     round-trip.
   - `tests/fixtures/picked_screen.schema.json` — JSON schema for the
     `picked_screen` block.
   - `tests/test_screens_invariant.py` — macos-gated paired
     coloured-square AV↔CGDirectDisplayID invariant test (skipped on CI
     without a Mac runner via `pytest.mark.macos`).

7. PyObjC added as **optional** dependency in `pyproject.toml`
   `[project.optional-dependencies]` under `macos`. Falls back to
   "main display only" on systems without it.

## Why

D1 in SHR-2212. The current `screen_index="0"` default is unsafe: on most
macOS hosts AVFoundation index 0 is the FaceTime camera. The user has
observed Screen Harness recording the camera instead of the screen.

## Impact

- New module + integration points in 4 existing modules (helpers, recorder,
  admin, run).
- New CLI subcommand `probe-screens`.
- New optional `[macos]` extra.
- Recording metadata gains `picked_screen` block — additive, not breaking.
- No removed APIs.
- Default behavior changes: `start_recording` no longer silently records
  AVFoundation index 0. On hosts where index 0 was actually the right
  screen, behavior is unchanged (picked_screen will resolve to the same
  device). On hosts where index 0 was the camera, the previous (buggy)
  behavior is replaced with correct screen selection.

## Plan

Follow COR-1500 TDD overlay: RED → GREEN → REFACTOR.

1. **RED**: write fixtures + failing unit tests for `probe_screens`
   parsing + `resolve_screen` matrix + camera-rejection.
2. **GREEN**: implement `screens.py` minimum to pass.
3. Wire `start_recording`, `recorder`, CLI, doctor.
4. **RED**: macos-gated invariant test stub.
5. **GREEN**: implement invariant test using `Quartz.CGDisplayBounds`
   round-trip; skip cleanly on non-Mac CI.
6. **REFACTOR**: tighten error messages, add CLI `--json` output, update
   README "Run The Safari/GitHub Demo" snippet to mention `screen=` /
   `app=` kwargs.
7. Run `uv run pytest -q` — all tests green.
8. Run `uv run python -m compileall -q src tests` — no syntax errors.
9. Run `af validate` — 0 issues.
10. Update README + SKILL.md helper API table to reflect new kwargs.

## Rollback

Revert this branch's commits on `main`. The new module and CLI subcommand
are isolated — removing them leaves prior behavior intact. The
`picked_screen` metadata block is additive; old `metadata.json` files are
still readable.

## Tests Gate (CI must pass)

- All existing tests still pass.
- New unit tests in `test_screens.py` pass on every locale fixture.
- Compileall clean.
- `af validate` 0 issues.
- macos-gated tests skip cleanly on Linux CI; pass on local Mac dev run
  (manual verification step before requesting review).

## Approval

- [ ] Approved by: <reviewer> on <date>

---

## Change History

| Date | Change | By |
|------|--------|----|
| 2026-05-11 | Initial CHG, implements approved PRP-2213 R2 | Claude Code |
