# Screen Harness

[![CI](https://github.com/frankyxhl/screen-harness/actions/workflows/ci.yml/badge.svg)](https://github.com/frankyxhl/screen-harness/actions/workflows/ci.yml)

Screen Harness is a CLI-first macOS tool for recording screen workflows and turning them into SOP videos and Markdown documents. It records an immutable `raw.mp4`, stores editable events in `timeline.json`, then renders captions, step titles, professional template overlays, highlights, clicks, and redactions into `final.mp4`.

The MVP is intentionally small: it proves the local recording-to-rendering loop before adding a daemon, global hotkeys, or cloud AI providers.

## What It Does

- Records the macOS screen with FFmpeg.
- Lets an agent or user add structured timeline events from Python helpers.
- Generates `sop.srt`, `sop.ass`, and `sop.md` from `timeline.json`.
- Renders `final.mp4` without mutating `raw.mp4`.
- Supports `debug` and `training` render templates.
- Lets highlight boxes choose a render color per event.
- Records the mouse cursor and mouse clicks in new screen captures when FFmpeg AVFoundation supports it.
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

## Run The Safari/GitHub Demo

The current demo script opens Safari, visits this repository, adds a white intro card with a countdown, shows numbered lower-corner step cards, and renders a video.

```bash
uv run screen-harness -c 'exec(open("examples/expense_sop.py").read())'
```

The script prints the recording directory and rendered `final.mp4` path when it completes. To find the latest demo later:

```bash
ls -td recordings/safari_github_repo_demo_* | head -1
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
uv run screen-harness render safari_github_repo_demo_20260506_150000
```

Use the professional training template explicitly:

```bash
uv run screen-harness render <recording_id> --template training
```

## Minimal Helper Example

```bash
uv run screen-harness -c '
start_recording("quick_demo")
intro("This video demonstrates the quick demo", subtitle="A short Screen Harness example", countdown=5)
step("Open the target app", note="Prepare the workflow for recording.")
caption("Open the target app and prepare the workflow.")
wait(3)
stop_recording()
render(template="training")
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

## CI/CD

GitHub Actions runs on pull requests and pushes to `main`:

- `test`: Python `3.14` with `pytest` and `compileall`.
- `alfred`: validates `rules/` with `uvx --from fx-alfred af validate`.
- `package`: builds source and wheel distributions with `uv build`, then uploads `dist/*` as the `screen-harness-dist` workflow artifact.
