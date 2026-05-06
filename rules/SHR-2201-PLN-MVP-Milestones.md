# PLN-2201: MVP Milestones

**Applies to:** SHR project
**Last updated:** 2026-05-06
**Last reviewed:** 2026-05-06
**Status:** Draft
**Related:** screen_harness_PRD.md, SHR-2200, SHR-2202

---

## What Is It?

This plan turns the Screen Harness PRD into implementation milestones. It narrows the first MVP to the smallest useful loop: record a macOS workflow, write timeline events, render the final SOP video, export Markdown, and reuse agent helpers.

---

## Goals

- Keep `raw.mp4` immutable and make `timeline.json` the source of truth.
- Prove a CLI-first workflow before adding GUI or global hotkeys.
- Separate deterministic media plumbing from AI caption quality work.
- Make each milestone independently demoable with concrete output files.


## Milestones

| # | Milestone | Recommended Duration | Status |
|---|-----------|----------------------|--------|
| 0 | Technical spike: FFmpeg recording and ASS burn-in | 1-2 days | Completed |
| 1 | MVP v0.1: CLI timeline-to-render loop | 1-2 weeks | Completed |
| 2 | AI SOP generation: transcription and rewrite pipeline | 1 week | Completed |
| 3 | Operator UX: hotkeys, recording management, light UI | 1-2 weeks | Pending |
| 4 | Productization: templates, exports, ScreenCaptureKit evaluation | TBD | Pending |

---

## Milestone 0: Technical Spike

**Goal:** Validate the risky local media assumptions before building abstractions.

**Deliverables:**

- Minimal Python or shell-driven FFmpeg wrapper.
- Main-display recording to `raw.mp4`.
- Microphone capture check, even if initially optional.
- Handwritten `sop.ass` burned into `final.mp4`.
- Basic rectangle overlay or redaction proof.

**Exit criteria:**

- A 30-second recording can be captured and rendered on the target macOS machine.
- Failure modes for missing FFmpeg and screen/microphone permissions are known.


## Milestone 1: MVP v0.1 CLI Loop

**Goal:** Deliver the first usable agent-facing product without depending on ASR quality.

**Deliverables:**

- Python package and CLI entrypoint.
- `init`, `doctor`, `-c`, `render`, `sop generate`, and helper-management commands.
- Recording directory lifecycle and `metadata.json`.
- `timeline.json` event model and safe writes.
- Helpers for `chapter`, `step`, `caption`, `click`, `highlight_region`, and `redact_region`.
- SRT and ASS generation from explicit caption events.
- Final video rendering with subtitles, step titles, highlights, clicks, and redactions.
- Markdown SOP export.
- `agent-workspace/agent_helpers.py` load-on-start behavior.
- Markdown domain skills under `agent-workspace/domain-skills/`.
- Agent-facing `SKILL.md` and setup/troubleshooting `install.md`.
- Example script based on the PRD expense-flow scenario.

**Exit criteria:**

- The example script produces `raw.mp4`, `timeline.json`, `sop.srt`, `sop.ass`, `sop.md`, `final.mp4`, and `metadata.json`.
- Re-rendering after a manual timeline edit works.
- A new helper added to `agent_helpers.py` is callable in the next `-c` run.


## Milestone 2: AI SOP Generation

**Goal:** Add AI value after the deterministic loop is stable.

**Deliverables:**

- Audio extraction.
- Pluggable transcription provider interface.
- Raw `transcript.srt`.
- SOP-caption rewrite from transcript plus timeline context.
- Provenance in `metadata.json` showing provider, model, and source inputs.
- Basic sensitive-text suggestion hooks without automatic redaction as a hard dependency.

**Exit criteria:**

- A recording with spoken narration can produce both raw transcript captions and cleaner SOP captions.
- The user can edit generated captions and re-render.


## Milestone 3: Operator UX

**Goal:** Make the tool practical for non-engineer SOP authors.

**Deliverables:**

- Global or local hotkeys for step, note, highlight, redact, and stop.
- Recording list/status commands.
- Better permission guidance in `doctor`.
- Optional lightweight menu bar or small control UI.
- Optional real-time preview captions that do not become the final source of truth.

**Exit criteria:**

- A user can record a short SOP without writing Python during the recording.
- The CLI-first path remains fully supported.


## Milestone 4: Productization

**Goal:** Prepare for repeatable team use.

**Deliverables:**

- SOP style templates.
- Multi-language subtitle variants.
- Stronger automatic redaction.
- Notion, Confluence, or richer Markdown export.
- ScreenCaptureKit evaluation or replacement plan.
- Versioning/review model for SOP artifacts.

**Exit criteria:**

- The team has enough evidence to decide whether to keep FFmpeg or move capture to ScreenCaptureKit.
- SOP outputs can fit a consistent team style.

---

## Recommended First Task Breakdown

1. Scaffold the Python package, CLI, config, and recording directory conventions.
2. Implement `doctor` and a minimal FFmpeg recording wrapper.
3. Implement timeline event persistence and timestamping.
4. Generate SRT/ASS from manual `caption()` events.
5. Render subtitles, highlights, clicks, and redactions from `timeline.json`.
6. Generate `sop.md` from timeline steps and captions.
7. Add helper loading and helper management commands.
8. Add `SKILL.md`, `install.md`, and the initial Markdown domain-skill convention.
9. Add the expense-flow example and acceptance test fixtures.

---

## Change History

| Date       | Change                                                                 | By    |
|------------|------------------------------------------------------------------------|-------|
| 2026-05-06 | Initial version                                                        | —     |
| 2026-05-06 | Filled recommended milestones and MVP task breakdown from PRD analysis | Codex |
| 2026-05-06 | Added browser-harness-inspired docs and domain-skill deliverables      | Codex |
| 2026-05-06 | Marked Milestone 0 completed after FFmpeg spike verification           | Codex |
| 2026-05-06 | Marked Milestone 1 completed after MVP CLI loop verification           | Codex |
| 2026-05-06 | Marked Milestone 2 completed after transcription, SOP generation, redaction, provenance, CLI, tests, and Trinity review | Codex |
