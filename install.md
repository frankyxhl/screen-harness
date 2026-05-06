# Screen Harness Install

## Local Editable Install

From the project root:

```bash
uv sync
uv run screen-harness init
uv run screen-harness doctor
```

For a global editable command:

```bash
uv tool install -e .
screen-harness doctor
```

## FFmpeg Requirements

Screen capture uses the default `ffmpeg` on PATH.

ASS subtitle burn-in requires FFmpeg with `subtitles` or `ass` plus `drawbox`. On this machine, that is:

```text
/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg
```

The renderer will prefer that binary when it exists. Override with:

```bash
SCREEN_HARNESS_FFMPEG=/path/to/ffmpeg screen-harness render <recording_id>
```

## macOS Permissions

Run:

```bash
screen-harness doctor
```

Expected MVP signals:

- `screen capture: ok`
- `render ffmpeg: ok`
- microphone may be `not detected`; microphone recording is optional in MVP v0.1.

## MVP AI SOP Generation

The first transcription provider is deterministic and offline. Put a manual transcript beside a recording:

```text
recordings/<recording_id>/manual_transcript.txt
```

Timed lines are preferred:

```text
00:00:01.000 --> 00:00:03.000 Open the target app.
00:00:03.500 --> 00:00:06.000 Submit the form.
```

Then run:

```bash
screen-harness transcribe <recording_id>
screen-harness sop ai-generate <recording_id>
screen-harness redact scan <recording_id>
screen-harness render <recording_id>
```

The derived files are `transcript.srt`, `transcript.json`, regenerated `sop.srt` / `sop.ass` / `sop.md`, and `redaction_suggestions.json`. Provenance is recorded under `metadata.json`.
