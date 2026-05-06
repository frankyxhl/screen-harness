# CHG-2206: Implement MVP CLI Loop

**Applies to:** SHR project
**Last updated:** 2026-05-06
**Last reviewed:** 2026-05-06
**Status:** Completed
**Related:** SHR-2200, SHR-2201, SHR-2202, SHR-2204, SHR-2205
**Date:** 2026-05-06
**Requested by:** Frank
**Priority:** Medium
**Change Type:** Normal

---

## What

Implement Milestone 1: the MVP v0.1 CLI timeline-to-render loop. This turns the Milestone 0 FFmpeg spike into a usable agent-facing workflow that can record, write timeline events, generate SRT/ASS/Markdown SOP outputs, render `final.mp4`, and load reusable agent helpers.


## Why

Milestone 0 proved local media assumptions. Milestone 1 delivers the first usable product loop from `SHR-2200` and `SHR-2201` without depending on ASR or AI caption rewriting.


## Impact Analysis

- **Systems affected:** Local Python package and project docs.
- **User-visible behavior:** Adds `screen-harness init`, `-c`, `render`, `sop generate`, and helper-management commands.
- **Data affected:** Creates local `recordings/` outputs and `agent-workspace/` helper files.
- **Downtime required:** No.
- **Rollback plan:** Revert the added Python modules/docs and remove generated local outputs; `raw.mp4` files generated during tests/spikes remain local and ignored.


## Implementation Plan

1. Add tests for project initialization and recording-directory conventions.
2. Add tests for timeline event creation, timestamping, and safe JSON writes.
3. Add tests for SRT/ASS/Markdown generation from explicit timeline events.
4. Add tests for helper namespace loading from `agent-workspace/agent_helpers.py`.
5. Add tests for `render()` refusing active recordings and preserving `raw.mp4`.
6. Implement the minimal helper/runtime state needed for `screen-harness -c`.
7. Implement CLI commands: `init`, `-c`, `render`, `sop generate`, `helpers diff`, `helpers open`, and `helpers reset`.
8. Add `SKILL.md`, `install.md`, initial domain/interaction skill placeholders, and an expense-flow example.
9. Verify the example produces `raw.mp4`, `timeline.json`, `sop.srt`, `sop.ass`, `sop.md`, `final.mp4`, and `metadata.json`.
10. Run Trinity fast-review after local verification.


## Testing / Verification

- `uv run pytest -q`
- `uv run python -m compileall -q src tests`
- `uv run screen-harness doctor`
- `uv run screen-harness init`
- Example `screen-harness -c` script that records a short screen sample and renders all MVP files.
- Manual timeline edit followed by re-render.
- Helper added to `agent-workspace/agent_helpers.py` is callable on the next `-c` run.
- `af validate`


## Approval

- [x] Reviewed by: Frank, via approved milestone order in this session.
- [x] Approved on: 2026-05-06.


## Execution Log

| Date | Action | Result |
|------|--------|--------|
| 2026-05-06 | Created CHG for Milestone 1 | Done |
| 2026-05-06 | Added timeline, captions, project init, helper runtime, and MVP CLI commands | `uv run pytest -q` passed |
| 2026-05-06 | Verified MVP `-c` recording/render flow | Produced `raw.mp4`, `timeline.json`, `sop.srt`, `sop.ass`, `sop.md`, `final.mp4`, and `metadata.json` |
| 2026-05-06 | Verified manual timeline edit and re-render | `raw.mp4` SHA-256 unchanged; edited caption appeared in regenerated SRT/ASS |
| 2026-05-06 | Verified agent helper load-on-next-run behavior | Temporary `m1_helper_probe()` returned `helper-loaded`; helper file reset afterward |
| 2026-05-06 | Added `SKILL.md`, `install.md`, expense example, domain skill, and interaction skills | Done |
| 2026-05-06 | Ran Trinity fast-review on M1 implementation | Review findings addressed: cleanup on `-c` exception, ffprobe OSError, stop timeout fallback, namespace control |
| 2026-05-06 | Added post-review regression tests and smoke run | `uv run pytest -q` now reports 20 passed; post-review `-c` flow produced all MVP files |

---

## Change History

| Date       | Change                                                     | By    |
|------------|------------------------------------------------------------|-------|
| 2026-05-06 | Initial version | — |
| 2026-05-06 | Filled Milestone 1 scope and approval | Codex |
| 2026-05-06 | Added M1 implementation, review, and verification evidence | Codex |
