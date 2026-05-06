# CHG-2204: Implement Milestone 0 Spike

**Applies to:** SHR project
**Last updated:** 2026-05-06
**Last reviewed:** 2026-05-06
**Status:** Completed
**Related:** SHR-2200, SHR-2201, SHR-2202, SHR-2203, SHR-2205
**Date:** 2026-05-06
**Requested by:** Frank
**Priority:** Medium
**Change Type:** Normal

---

## What

Implement Milestone 0 for Screen Harness: a minimal FFmpeg technical spike that proves main-display recording, ASS subtitle burn-in, and a basic rectangle overlay/redaction path before the full MVP package is built.


## Why

`SHR-2201` intentionally puts a technical spike before the MVP milestone so local media assumptions are validated early. The spike reduces risk around macOS AVFoundation capture, FFmpeg availability, permissions, output paths, and subtitle/overlay rendering.


## Impact Analysis

- **Systems affected:** Local working tree only; no external services.
- **User-visible behavior:** Adds local project files for a minimal Python package and spike script/tests.
- **Data affected:** May create local test/spike recording outputs under ignored recording or temporary directories.
- **Downtime required:** No.
- **Rollback plan:** Remove the added spike/package files and generated local outputs; no persistent external state is changed.


## Implementation Plan

1. Scaffold the minimal package/test structure needed for Milestone 0.
2. Add tests for FFmpeg discovery/device parsing and render command construction before implementation.
3. Implement a minimal FFmpeg recorder wrapper for main-display capture.
4. Implement ASS burn-in and a basic rectangle overlay/redaction render path.
5. Add `doctor` output that reports FFmpeg version, AVFoundation screen device visibility, and microphone availability.
6. Run a low-risk local verification using generated/sample media where possible.
7. Record known FFmpeg permission/device failure modes in project docs or implementation notes.


## Testing / Verification

- Unit tests for command construction and device-output parsing.
- `af validate`.
- `ffmpeg -hide_banner -version`.
- `ffmpeg -hide_banner -f avfoundation -list_devices true -i ""` for local device discovery.
- A render smoke test using a generated short sample source, ASS subtitles, and a rectangle overlay.
- If practical, a short real screen recording smoke test; if macOS permissions block it, document the exact failure and `doctor` guidance.


## Approval

- [x] Reviewed by: Frank, via approved COR-1202 routine in this session.
- [x] Approved on: 2026-05-06.


## Execution Log

| Date | Action | Result |
|------|--------|--------|
| 2026-05-06 | Created CHG for Milestone 0 | Done |
| 2026-05-06 | Added minimal package, tests, doctor, recorder command builder, ASS render smoke, and spike CLI | `uv run pytest -q` passed |
| 2026-05-06 | Verified generated-media render smoke | `.screen-harness-spike/final.mp4`, 640x360, 30 fps, 3.0s |
| 2026-05-06 | Verified real 30-second screen recording | `.screen-harness-spike/screen-30s.mp4`, 1920x1080, 30 fps, 29.93s |
| 2026-05-06 | Recorded FFmpeg findings | See SHR-2205 |
| 2026-05-06 | Ran Trinity fast-review on M0 implementation | PASS from glm and deepseek; non-blocking hardening items addressed |
| 2026-05-06 | Added post-review hardening tests | `uv run pytest -q` now reports 10 passed |

---

## Change History

| Date       | Change                                                       | By    |
|------------|--------------------------------------------------------------|-------|
| 2026-05-06 | Initial version | — |
| 2026-05-06 | Filled Milestone 0 implementation scope and approval | Codex |
| 2026-05-06 | Updated execution log with Milestone 0 verification evidence | Codex |
| 2026-05-06 | Added code-review and post-review hardening evidence | Codex |
