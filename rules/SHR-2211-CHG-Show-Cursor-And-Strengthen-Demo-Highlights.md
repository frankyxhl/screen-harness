# CHG-2211: Show Cursor And Strengthen Demo Highlights

**Applies to:** SHR project
**Last updated:** 2026-05-06
**Last reviewed:** 2026-05-06
**Status:** Proposed
**Date:** 2026-05-06
**Requested by:** —
**Priority:** Medium
**Change Type:** Normal

---

## What

Improve the recorded Safari/GitHub demo by making focus highlights more visible and by recording the mouse cursor/clicks in the raw screen capture.

Changes:

- Enable AVFoundation cursor capture by default:
  - `-capture_cursor true`
  - `-capture_mouse_clicks true`
- Record the cursor/click capture settings in `metadata.json`.
- Strengthen default demo highlights:
  - default highlight color from `blue@0.35` to `blue@0.60`;
  - default highlight thickness from `4` to `10`;
  - allow per-event `highlight_region(..., thickness=...)` customization.
- Rerun the Safari/GitHub demo after implementation.

## Why

The first professional training render improved the intro and step-card presentation, but visual review found two remaining gaps:

- The blue focus rectangle is still too subtle on GitHub's light UI.
- Viewers cannot see where the operator's mouse is, which makes the walkthrough harder to follow.

FFmpeg's AVFoundation demuxer already supports cursor and click capture on this machine, so the low-risk first implementation should use native capture before adding custom cursor overlays or animated click effects.

## Impact Analysis

- **Systems affected:** recorder command builder, recording helper metadata, highlight event helper, render drawbox conversion, demo script, tests, README/SKILL docs.
- **User-visible behavior:** New recordings show the system cursor/clicks when the local FFmpeg AVFoundation device supports it. Default highlight boxes are thicker and more visible.
- **Data affected:** `metadata.json` records additive `capture_cursor` and `capture_mouse_clicks` booleans. `timeline.json` highlight events may include optional `thickness`.
- **Compatibility:** Existing recordings and timelines still render. Old highlight events without `thickness` get the stronger default at render time.
- **Rollback plan:** Remove AVFoundation cursor flags, remove metadata fields, restore previous highlight defaults, and rerun the demo.

## Implementation Plan

1. Add failing tests for AVFoundation cursor/click flags in `build_screen_record_command`.
2. Add helper tests for default highlight color/thickness and per-event thickness override.
3. Implement recorder options:
   - default `capture_cursor=True`;
   - default `capture_mouse_clicks=True`;
   - explicit disabling support for tests/future callers.
4. Update `start_recording()` metadata with the capture settings.
5. Update `highlight_region()` and `_drawboxes()` to carry `thickness`.
6. Update docs and the Safari demo to use the stronger highlight values.
7. Validate with Python 3.14 tests, compile, and `af validate`.
8. Rerun the Safari/GitHub demo with Safari foregrounded and Chrome hidden.


## Testing / Verification

- `uv run --python 3.14 pytest -q`
- `uv run --python 3.14 python -m compileall -q src tests examples`
- `af validate`
- Manual demo output:
  - new `recordings/safari_github_repo_demo_*/final.mp4`
  - metadata shows `render_template = training`
  - metadata shows cursor/click capture enabled.


## Out Of Scope

- Custom cursor rendering independent of the OS cursor.
- Animated click ripple or pointer trail overlays.
- Named theme files for highlight styles.
- Browser privacy automation beyond hiding Chrome and using Safari for this demo.

---

## Change History

| Date | Change | By |
|------|--------|----|
| 2026-05-06 | Initial version | — |
| 2026-05-06 | Filled implementation scope from demo visual review | Codex |
