---
name: screen-harness
description: Record macOS screen workflows and generate SOP videos/documents through the Screen Harness CLI.
---

# Screen Harness

Use this skill when the user wants to record a screen workflow, add timeline events, render SOP subtitles/overlays, or reuse local helper functions.

## Usage

```bash
screen-harness init
screen-harness doctor
screen-harness -c '
start_recording("demo")
step("Open the target app")
caption("Open the target app and prepare the workflow.")
wait(3)
stop_recording()
render()
'
screen-harness transcribe <recording_id>
screen-harness sop ai-generate <recording_id>
screen-harness redact scan <recording_id>
```

## Workflow

1. Run `screen-harness doctor`.
2. Use `screen-harness -c` with helpers pre-imported.
3. Keep `raw.mp4` immutable.
4. Edit `timeline.json` when needed.
5. Re-run `screen-harness render <recording_id>` after timeline edits.
6. Put reusable executable helpers in `agent-workspace/agent_helpers.py`.
7. Put durable process knowledge in `agent-workspace/domain-skills/<system>/<flow>.md`.
8. For AI-style SOP generation, place an MVP manual transcript in `recordings/<id>/manual_transcript.txt`, run `transcribe`, then run `sop ai-generate`.

## Helpers

- `start_recording(name)`
- `stop_recording()`
- `wait(seconds)`
- `wait_for_user(message)`
- `chapter(title)`
- `step(title)`
- `caption(text, duration=None)`
- `click(x, y, label=None)`
- `highlight_region(x, y, w, h, text=None, duration=3.0)`
- `redact_region(x, y, w, h, reason=None, duration=None)`
- `render()`
- `generate_sop_captions()`
- `generate_ai_sop()`
- `generate_markdown_sop()`
- `transcribe()`
- `scan_redactions()`

## Manual Transcript Format

Use timed lines when possible:

```text
00:00:01.000 --> 00:00:03.000 Open the target app.
00:00:03.500 --> 00:00:06.000 Submit the form.
```

Plain lines are also accepted and are spaced four seconds apart.

## Notes

- Default FFmpeg can record screen, but this local machine uses `ffmpeg-full` for ASS burn-in rendering.
- Microphone capture is optional until `doctor` detects an audio device; the MVP transcription provider uses `manual_transcript.txt`.
- Do not add a daemon for normal MVP work; use one later only for hotkeys or multi-process control.
