# CHG-2207: Implement AI SOP Generation Pipeline

**Applies to:** SHR project
**Last updated:** 2026-05-06
**Last reviewed:** 2026-05-06
**Status:** Completed
**Related:** SHR-2200, SHR-2201, SHR-2202, SHR-2206
**Date:** 2026-05-06
**Requested by:** Frank
**Priority:** Medium
**Change Type:** Normal

---

## What

Implement Milestone 2: AI SOP generation pipeline. This adds a deterministic transcription/rewrite path around the existing `raw.mp4` + `timeline.json` loop:

- Extract audio from `raw.mp4` when an audio stream exists.
- Provide a pluggable transcription provider interface.
- Ship an offline manual-transcript provider for MVP verification.
- Generate raw `transcript.srt`.
- Generate cleaner SOP captions from transcript segments plus existing timeline steps.
- Record provenance in `metadata.json`.
- Generate sensitive-text redaction suggestions without mutating `raw.mp4` or requiring automatic redaction.

## Why

`SHR-2201` defines Milestone 2 as the first AI-value layer after the deterministic MVP loop. The local machine currently has no detected microphone device, so M2 must not depend on live audio capture or a cloud ASR service to be testable. A manual/offline provider proves the contracts, file outputs, metadata, and edit/re-render workflow while leaving a narrow interface for real ASR and LLM providers later.

## Impact Analysis

- **Systems affected:** Local Python package, CLI, recording output schema, docs, tests.
- **User-visible behavior:** Adds commands for transcription, AI-style SOP caption generation, and redaction suggestion scanning.
- **Data affected:** May create `audio.wav`, `transcript.srt`, `transcript.json`, `sop.srt`, `sop.ass`, `sop.md`, `redaction_suggestions.json`, and additional provenance fields in `metadata.json`.
- **Downtime required:** No.
- **Rollback plan:** Revert the added M2 modules/CLI/docs/tests. Existing M1 recordings remain valid because `raw.mp4` and `timeline.json` stay unchanged and M2 outputs are derived files.

## Implementation Plan

1. Add tests for manual transcript parsing and raw `transcript.srt` generation.
2. Add tests for audio extraction behavior when a recording has or lacks an audio stream.
3. Add tests for SOP-caption generation from transcript segments and timeline steps.
4. Add tests for metadata provenance updates.
5. Add tests for sensitive-text suggestion scanning.
6. Add CLI dispatch for `transcribe`, `sop ai-generate`, and `redact scan`.
7. Implement transcription provider interface and deterministic manual provider.
8. Implement SOP rewrite heuristics suitable for MVP fallback.
9. Update agent-facing docs and milestone records.
10. Verify with local tests, `doctor`, `af validate`, and Trinity fast-review.


## Testing / Verification

- `uv run pytest -q`
- `uv run python -m compileall -q src tests`
- `uv run screen-harness doctor`
- Manual transcript fixture through `screen-harness transcribe <recording_id>`
- SOP caption generation through `screen-harness sop ai-generate <recording_id>`
- Sensitive text scan through `screen-harness redact scan <recording_id>`
- `af validate`


## Approval

- [x] Reviewed by: Frank, via approved ordered milestone execution in this session.
- [x] Approved on: 2026-05-06.


## Execution Log

| Date | Action | Result |
|------|--------|--------|
| 2026-05-06 | Created CHG for Milestone 2 | Done |
| 2026-05-06 | Filled M2 scope and started implementation | In progress |
| 2026-05-06 | Added manual transcription provider, audio extraction contract, raw transcript outputs, AI SOP generation, redaction scan, provenance, and CLI commands | `uv run pytest -q` passed |
| 2026-05-06 | Verified M2 CLI sequence on demo recording | Produced `transcript.srt`, `transcript.json`, regenerated SOP assets, `redaction_suggestions.json`, updated `metadata.json`, and rendered `final.mp4` |
| 2026-05-06 | Ran Trinity fast-review R1 | PASS synthesis; addressed hardcoded `ffprobe`, hidden transcription side-effect, atomic writes, idempotency coverage, and redaction confidence/dedup notes |
| 2026-05-06 | Ran Trinity fast-review R2 after fixes | PASS from glm and deepseek; addressed remaining non-blocking atomic-write consistency notes |
| 2026-05-06 | Final local verification | `34` tests passed; `compileall`, `doctor`, M2 CLI sequence, and `af validate` passed |

---

## Change History

| Date | Change | By |
|------|--------|----|
| 2026-05-06 | Initial version | — |
| 2026-05-06 | Filled Milestone 2 scope and approval | Codex |
| 2026-05-06 | Completed M2 implementation, review, and verification evidence | Codex |
