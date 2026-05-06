# Screen Harness

Screen Harness is a CLI-first macOS tool for recording screen workflows and turning them into SOP videos and Markdown documents. It records an immutable `raw.mp4`, stores editable events in `timeline.json`, then renders captions, step titles, highlights, clicks, and redactions into `final.mp4`.

The MVP is intentionally small: it proves the local recording-to-rendering loop before adding a daemon, global hotkeys, or cloud AI providers.

## What It Does

- Records the macOS screen with FFmpeg.
- Lets an agent or user add structured timeline events from Python helpers.
- Generates `sop.srt`, `sop.ass`, and `sop.md` from `timeline.json`.
- Renders `final.mp4` without mutating `raw.mp4`.
- Loads reusable helpers from `agent-workspace/agent_helpers.py`.
- Supports manual/offline transcript input for AI-style SOP caption generation.
- Scans transcript and timeline text for sensitive strings such as emails and tokens.

## Install

```bash
uv sync
uv run screen-harness init
uv run screen-harness doctor
```

Expected MVP signals:

```text
screen capture: ok
render ffmpeg: ok
```

Microphone can be `not detected`; the current MVP works without microphone input.

## Run The Chrome/GitHub Demo

The current demo script opens Google Chrome, visits this repository, adds subtitles and highlights, then renders a video.

```bash
uv run screen-harness -c 'exec(open("examples/expense_sop.py").read())'
```

The script prints the recording directory and rendered `final.mp4` path when it completes. To find the latest demo later:

```bash
ls -td recordings/chrome_github_repo_demo_* | head -1
```

Expected files in the recording directory:

```text
raw.mp4
timeline.json
sop.srt
sop.ass
sop.md
final.mp4
metadata.json
ffmpeg.log
```

To re-render after editing captions or events:

```bash
uv run screen-harness render <recording_id>
```

Example:

```bash
uv run screen-harness render chrome_github_repo_demo_20260506_150000
```

## Minimal Helper Example

```bash
uv run screen-harness -c '
start_recording("quick_demo")
step("Open the target app")
caption("Open the target app and prepare the workflow.")
wait(3)
stop_recording()
render()
'
```

## AI SOP Generation

Create a manual transcript beside a recording:

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
uv run screen-harness transcribe <recording_id>
uv run screen-harness sop ai-generate <recording_id>
uv run screen-harness redact scan <recording_id>
uv run screen-harness render <recording_id>
```

## Project Layout

```text
src/screen_harness/       CLI, recording, rendering, timeline, transcript, SOP logic
examples/                 Runnable demo scripts
agent-workspace/          User-editable helper and domain-skill workspace
interaction-skills/       Reusable interaction notes
rules/                    Alfred planning and change records
tests/                    Unit tests
```

## Development

```bash
uv run pytest -q
uv run python -m compileall -q src tests
af validate
```
