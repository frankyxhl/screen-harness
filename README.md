# Screen Harness

[![CI](https://github.com/frankyxhl/screen-harness/actions/workflows/ci.yml/badge.svg)](https://github.com/frankyxhl/screen-harness/actions/workflows/ci.yml)

Screen Harness is a CLI-first macOS tool for recording screen workflows and turning them into SOP videos and Markdown documents. It records an immutable `raw.mp4`, stores editable events in `timeline.json`, then renders an intro card, frosted-glass step overlays, highlight strokes, an outro/end card, and Markdown SOP from one timeline.

The MVP stays intentionally small: it proves the local recording → rendering loop before adding a daemon, global hotkeys, or cloud AI providers.

## What It Does

- Records the macOS screen with FFmpeg (AVFoundation).
- Optionally crops the recording to a single window region (no Dock, no menu bar) via the `region=(x, y, w, h)` argument on `start_recording`.
- Lets an agent or user add structured timeline events from Python helpers (`intro`, `step`, `caption`, `highlight_region`, `outro`, …).
- Generates `sop.srt`, `sop.ass`, and `sop.md` from `timeline.json`.
- Renders `final.mp4` without mutating `raw.mp4`. The training template produces:
  - **Intro card** — branded charcoal background, wordmark, title, "STARTING IN" countdown.
  - **Main recording** — fixed-position frosted-glass step card (FFmpeg `boxblur` over the underlying frame, off-white tint) with a teal step number and dark title; teal highlight strokes around the regions you call out.
  - **Outro card** — held end frame with title, optional subtitle, and the project URL in the accent color.
- Loads reusable helpers from `agent-workspace/agent_helpers.py`.
- Supports manual/offline transcript input for AI-style SOP caption generation.
- Scans transcript and timeline text for sensitive strings such as emails and tokens.

The visual system uses Color Hunt's "DevDark" palette: `#222831` charcoal, `#393E46` graphite, `#00ADB5` teal accent, `#EEEEEE` off-white. The same palette drives intro, step card, highlight strokes, and outro for visual continuity.

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

The current demo script forces Safari to a deterministic `1920×1080` window, derives the crop region from Safari's actual bounds (so the recording excludes the Dock and menu bar), opens the repository on github.com, calls out the URL bar / repo header / file list / README, and finally holds a 4-second outro card with the project URL.

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
intro.ass
intro-source.mp4
intro.mp4
main.mp4
outro.ass
outro-source.mp4
outro.mp4
final.mp4
metadata.json
ffmpeg.log
```

To re-render after editing captions or events:

```bash
uv run screen-harness render <recording_id>
```

Use the professional training template explicitly:

```bash
uv run screen-harness render <recording_id> --template training
```

## Helper API (used inside `screen-harness -c '<python>'`)

| Helper | Purpose |
|--------|---------|
| `start_recording(name, *, region=None, capture_cursor=True, capture_mouse_clicks=True)` | Start FFmpeg AVFoundation capture. `region=(x, y, w, h)` crops to that screen rect — combine with AppleScript-driven window placement to record a single app. |
| `stop_recording()` | Finalize the capture and update `metadata.json`. |
| `wait(seconds)`, `wait_for_user(msg)` | Pace the script. |
| `intro(title, *, subtitle=None, countdown=5)` | Configure the pre-roll intro card. |
| `chapter(title)` | Mark a chapter (currently ignored by training render). |
| `step(title, *, note=None, number=None)` | A timeline step; renders inside the frosted-glass step card. |
| `caption(text, *, duration=None)` | A caption track entry → `sop.srt`. |
| `click(x, y, *, label=None)` | Draw a small red dot at a click position. |
| `highlight_region(x, y, w, h, *, text=None, duration=3.0, color=None, thickness=None)` | Draw a colored stroke around a region (defaults to teal `#00ADB5`). |
| `redact_region(x, y, w, h, *, reason=None, duration=None)` | Black-fill a sensitive region. |
| `outro(title="Thanks for watching", *, subtitle=None, url=None, duration=4.0)` | Hold a branded end card after the main recording. |
| `render(*, template="training" | "debug")` | Generate SOP assets and `final.mp4`. |
| `transcribe()`, `generate_ai_sop()`, `scan_redactions()` | Transcript + AI SOP + redaction scan. |

## Minimal Helper Example

```bash
uv run screen-harness -c '
start_recording("quick_demo")
intro("This video demonstrates the quick demo", subtitle="A short Screen Harness example", countdown=5)
step("Open the target app", note="Prepare the workflow for recording.")
caption("Open the target app and prepare the workflow.")
wait(3)
outro("Thanks for watching", url="github.com/frankyxhl/screen-harness")
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
tests/                    Unit, BDD, and end-to-end tests
SKILL.md                  AI-agent oriented install + usage prompt
```

## Development

```bash
uv run pytest -q
uv run --with pytest-cov pytest --cov=src/screen_harness --cov-report=term-missing -q
uv run python -m compileall -q src tests
af validate
```

Current test posture: **90 tests, ~86% line coverage** across unit, BDD-style, and FFmpeg-backed end-to-end tests (the e2e tests skip cleanly when FFmpeg lacks the `subtitles` / `drawbox` filters).

## CI/CD

GitHub Actions runs on pull requests and pushes to `main`:

- `test`: Python `3.14` with `pytest` and `compileall`.
- `alfred`: validates `rules/` with `uvx --from fx-alfred af validate`.
- `package`: builds source and wheel distributions with `uv build`, then uploads `dist/*` as the `screen-harness-dist` workflow artifact.

## Use as a Claude Skill

`SKILL.md` at the repo root is an AI-agent oriented install + usage prompt — drop the file (or its frontmatter+body) into a Claude Code or Claude Agent SDK skill bundle and the model can drive Screen Harness end-to-end without further hand-holding.
