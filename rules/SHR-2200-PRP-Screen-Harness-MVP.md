# PRP-2200: Screen Harness MVP

**Applies to:** SHR project
**Last updated:** 2026-05-06
**Last reviewed:** 2026-05-06
**Status:** Approved
**Related:** screen_harness_PRD.md, SHR-2201, SHR-2202
**Reviewed by:** Trinity fast-review R2: glm PASS, deepseek PASS

---

## What Is It?

Screen Harness MVP is a CLI-first macOS tool that lets a user or coding agent record a screen workflow, write structured timeline events, render a training-ready video, and export a Markdown SOP from the same timeline. The MVP intentionally proves the deterministic recording-to-rendering loop before adding heavier AI automation.

---

## Problem

The PRD defines the right product direction, but its P0 scope combines at least two risk profiles:

- deterministic system work: recording, timeline persistence, helper loading, rendering, and file outputs;
- AI quality work: transcription, SOP rewriting, sensitive-information detection, and caption timing.

If both are treated as the first implementation target, the team can spend time debugging provider quality while the core product loop is still unstable. The MVP should instead establish a narrow, reliable loop where an agent can author clean captions and annotations directly, then add ASR and AI rewriting once the timeline and renderer are trusted.

---

## Scope

**In scope for MVP v0.1:**

- macOS main-display recording through FFmpeg.
- Optional microphone capture when FFmpeg can access the selected device.
- `screen-harness init`, `screen-harness doctor`, and `screen-harness -c '<python>'`.
- Recording directory creation under `recordings/<recording_id>/`, where `recording_id` defaults to `{slugified_name}_{YYYYMMDD_HHMMSS}`.
- Preservation of `raw.mp4`; generated files never mutate the source video.
- `timeline.json` as the source of truth.
- Timeline and flow helpers: `wait`, `wait_for_user`, `chapter`, `step`, `caption`, `click`, `highlight_region`, and `redact_region`.
- Post-production rendering to `final.mp4` with visible subtitles, simple highlights, click markers, and rectangle redactions.
- `sop.srt`, `sop.ass`, `sop.md`, and `metadata.json` generated from the timeline.
- `agent-workspace/agent_helpers.py` loaded at command startup.
- Markdown domain skills under `agent-workspace/domain-skills/` for reusable SOP playbooks.
- Markdown interaction skills under `interaction-skills/` for reusable recording mechanics.
- Agent-facing `SKILL.md` and setup/troubleshooting `install.md`.
- Helper management commands: `helpers diff`, `helpers open`, and `helpers reset`.

**Out of scope for MVP v0.1:**

- Automatic transcription and AI rewriting. This starts in Milestone 2.
- Global hotkeys and menu bar UI. These start in Milestone 3.
- Window-only capture, system audio capture, pause/resume recording, ScreenCaptureKit, timeline GUI, cloud collaboration, Notion/Confluence export, and automatic sensitive-information detection.


## Proposed Solution

Build the first release as a thin Python package around FFmpeg and structured JSON.

Borrow the browser-harness model from SHR-2202: a small protected core, `-c` as the primary agent interface, editable workspace helpers, and plain-file skills. Do not copy browser-harness code; the shared value is the boundary design.

### Command Surface

```bash
screen-harness init
screen-harness doctor
screen-harness -c 'start_recording("demo"); step("Open app"); caption("Open the target app."); stop_recording(); render()'
screen-harness render <recording_id>
screen-harness sop generate <recording_id>
screen-harness helpers diff
screen-harness helpers open
screen-harness helpers reset
```

### Architecture

- `screen_harness/run.py`: CLI entrypoint and `-c` execution harness.
- `screen_harness/helpers.py`: agent-facing API.
- `screen_harness/recorder.py`: FFmpeg subprocess lifecycle.
- `screen_harness/timeline.py`: event model, timestamping, safe JSON writes.
- `screen_harness/captions.py`: SRT and ASS generation from caption events.
- `screen_harness/render.py`: FFmpeg filter generation for subtitles, highlights, click markers, and redactions.
- `screen_harness/admin.py`: init, doctor, device checks, and recording-directory checks.
- `agent-workspace/agent_helpers.py`: user-visible helper extension file.
- `agent-workspace/domain-skills/<system>/<flow>.md`: Markdown SOP playbooks learned from repeated workflows.
- `interaction-skills/`: Markdown guidance for reusable recording mechanics.
- `SKILL.md`: agent usage guide.
- `install.md`: setup and troubleshooting guide.

No daemon is included in MVP v0.1. Recording can be owned by the current `-c` process. Add a daemon later only when hotkeys, menu bar controls, live preview, or multi-process control require it.

### MVP Behavior

1. `init` creates `recordings/`, `agent-workspace/agent_helpers.py`, `agent-workspace/domain-skills/`, and `interaction-skills/`. MVP v0.1 does not require a project config file; use environment variables and `.env` only when needed.
2. `doctor` checks FFmpeg availability, output path writability, likely macOS permission blockers, and microphone/device visibility.
3. `start_recording(name)` creates a timestamped recording directory and launches FFmpeg.
4. Timeline helpers append timestamped events relative to recording start.
5. `stop_recording()` stops FFmpeg and finalizes `raw.mp4` plus `metadata.json`.
6. `wait(seconds)` sleeps for a fixed duration. `wait_for_user(message)` prints the message and blocks until the user presses Enter, allowing agent scripts to pause while a human performs manual UI work. During active recording, FFmpeg keeps recording while `wait_for_user()` blocks.
7. Caption generation derives `sop.srt` and `sop.ass` from explicit `caption()` events.
8. Markdown generation writes `sop.md` with title, ordered steps, captions, and timestamps.
9. `render()` is the default full-output pipeline: it ensures `sop.srt`, `sop.ass`, and `sop.md` are generated, then renders `final.mp4`. `screen-harness sop generate <recording_id>` exists for regenerating SOP files without rendering video.
10. `render()` requires a stopped recording. If called while recording is active, it raises an actionable error and does not implicitly stop the recording.
11. Rendering reads `timeline.json` and writes `final.mp4` without changing `raw.mp4`. Step titles render as a visible title overlay derived from `step` events, separate from normal caption text when possible.
12. Domain skills capture durable workflow knowledge as Markdown; Python helpers capture only executable reusable behavior.
13. If FFmpeg exits unexpectedly, the tool preserves the recording directory, writes the failure into `metadata.json`, and leaves any partial `raw.mp4` in place for inspection.

### Minimal Metadata

`metadata.json` must contain at least:

- `recording_id`
- `name`
- `created_at`
- `recording_started_at`
- `recording_stopped_at`
- `duration`
- `status`
- `raw_video`
- `ffmpeg_path`
- `ffmpeg_version`
- `canvas` when known: width, height, fps
- `error` when recording or rendering fails

### Event Defaults

- `redact_region(..., duration=None)` means the redaction lasts until the end of the recording.
- `highlight_region(..., duration=3.0)` keeps the PRD default.
- `caption(..., duration=None)` uses a 4.0 second default duration unless the next caption starts earlier.
- A recording with zero `caption()` events still generates empty-but-valid `sop.srt` and `sop.ass` files and a `sop.md` built from step events.

### Acceptance Criteria

- A user can run a single `screen-harness -c` script and get:
  - `raw.mp4`
  - `timeline.json`
  - `sop.srt`
  - `sop.ass`
  - `sop.md`
  - `final.mp4`
  - `metadata.json`
- `raw.mp4` remains unchanged after repeated renders.
- Manual edits to `timeline.json` can be rendered again.
- A sample expense-flow script produces a coherent final video with at least one step title, one subtitle, one highlight, one click marker, and one redaction.
- Helper functions added to `agent-workspace/agent_helpers.py` are available on the next CLI run.
- `doctor` gives actionable output when FFmpeg or permissions are missing.
- `wait_for_user()` keeps recording active while waiting for a human to continue.
- Calling `render()` before `stop_recording()` fails clearly without mutating `raw.mp4`.


## Open Questions

None blocking MVP v0.1. Recommended defaults from the PRD:

1. Screen capture: main display only.
2. System audio: out of scope.
3. Transcription provider: out of scope until Milestone 2.
4. Cloud upload: disabled by default; future AI providers require explicit config.
5. Timeline editing: JSON editing first.
6. Hotkeys: out of scope until Milestone 3.
7. SOP export: Markdown first.
8. Agent helper edits: allowed for trusted local agents; visible through `helpers diff`.
9. Branding: no logo or intro/outro in MVP.
10. Multi-user review/versioning: out of scope.

---

## Change History

| Date       | Change                                                                                                 | By    |
|------------|--------------------------------------------------------------------------------------------------------|-------|
| 2026-05-06 | Initial version | — |
| 2026-05-06 | Filled MVP scope and acceptance criteria from PRD analysis | Codex |
| 2026-05-06 | Added browser-harness reference principles and no-daemon MVP boundary | Codex |
| 2026-05-06 | Resolved fast-review findings on output pipeline, helper scope, skills, metadata, and failure defaults | Codex |
| 2026-05-06 | Clarified final R2 review notes on render state, durations, domain skill paths, and pause/resume scope | Codex |
