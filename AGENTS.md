# Screen Harness — Agent Instructions

Screen Harness is a CLI-first macOS tool for recording screen workflows and
turning them into SOP videos and Markdown documents. It records an immutable
`raw.mp4`, stores editable events in `timeline.json`, then renders an intro
card, frosted-glass step overlays, teal highlight strokes, an outro card, and
Markdown SOP from a single timeline.

## When to use this project

Use Screen Harness when you need to:

- Record a macOS screen workflow (process tour, bug reproduction, feature demo)
  and produce a polished video with step overlays, callouts, and branded cards.
- Generate a Markdown SOP document from a recording timeline (with or without
  audio transcription).
- Add structured annotations — intro, steps, captions, highlights, redactions,
  outro — to an existing recording without re-shooting (edit `timeline.json`
  and re-render).

Do **not** use Screen Harness for live transcription / streaming, multi-display
recording, or anything requiring a persistent background daemon — those are
explicitly out of MVP scope.

## Install

One-time setup per machine:

```bash
brew install ffmpeg ffmpeg-full      # capture (avfoundation) + render (libass filters)
uv sync                              # install dependencies into .venv
uv run screen-harness init           # create recordings/, agent-workspace/, etc.
uv run screen-harness doctor         # verify ffmpeg + AVFoundation
```

Homebrew's regular `ffmpeg` 8.x no longer bundles libass, so rendering needs
the keg-only `ffmpeg-full` (auto-preferred at
`/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg`, or set `SCREEN_HARNESS_FFMPEG`).

`doctor` should print at least:

```text
screen capture: ok
render ffmpeg: ok
```

Microphone may show as `not detected` — that's fine for the MVP. Screen
Recording permission must be granted for whichever process runs `ffmpeg`
(Terminal, iTerm, Claude Code …) via System Settings → Privacy & Security →
Screen & System Audio Recording the first time.

## Recording script shape

Every Screen Harness recording is a single Python script executed via
`screen-harness -c '<python>'`. All helpers are pre-imported into the script
namespace.

```python
start_recording("my_demo", region=(0, 25, 1920, 1055))   # optional crop
intro("My Demo", subtitle="A short tour.", countdown=5)
step("Open the app", note="Launch and bring it to the foreground.")
caption("Open the app and prepare the workflow.", duration=3.0)
wait(3.0)
highlight_region(150, 150, 720, 42, text="Header", duration=3.0)
outro("Thanks for watching",
      subtitle="Find the project on GitHub",
      url="github.com/frankyxhl/screen-harness",
      duration=4.0)
stop_recording()
render(template="training")
```

Run it:

```bash
uv run screen-harness -c "$(cat my_demo.py)"
```

Re-render anytime after editing `timeline.json`:

```bash
uv run screen-harness render <recording_id> --template training
```

## Helper API

| Helper | What it does |
|--------|--------------|
| `start_recording(name, *, screen=None, app=None, region=None, capture_cursor=True, capture_mouse_clicks=True, mic=None)` | Begin AVFoundation capture. `screen` is an int AV index, `"display:N"` (1-indexed), or `None` (auto-picks main display). `app="Safari"` resolves to the display containing that app's front window. `region=(x, y, w, h)` crops to a screen rect. |
| `stop_recording()` | End capture, finalize `metadata.json`. |
| `wait(seconds)` / `wait_for_user(msg)` | Pace the script. |
| `intro(title, *, subtitle=None, countdown=5)` | Pre-roll intro card on charcoal background. |
| `chapter(title)` | Logical chapter marker (currently informational only). |
| `step(title, *, note=None, number=None)` | A frosted-glass step card overlay during this beat. |
| `caption(text, *, duration=None)` | Caption track entry → `sop.srt`. |
| `click(x, y, *, label=None)` | Red dot click marker. |
| `highlight_region(x, y, w, h, *, text=None, duration=3.0, color="0x00ADB5@0.85", thickness=6)` | Teal stroke around a region. Coordinates are in the cropped frame. |
| `redact_region(x, y, w, h, *, reason=None, duration=None)` | Black-fill sensitive content at render time. |
| `outro(title="Thanks for watching", *, subtitle=None, url=None, duration=4.0)` | Held end card with project URL. |
| `render(*, template="training" \| "debug")` | Build SOP assets + `final.mp4`. |
| `transcribe()` / `generate_ai_sop()` / `scan_redactions()` | Manual-transcript-driven SOP + redaction scan. |

Coordinates for `highlight_region`, `click`, and `redact_region` are in the
**cropped frame** coordinate system when `region=` is used — `(0, 0)` is the
window's top-left, not the screen origin.

## AI SOP generation

Drop a manual transcript beside a recording and run the SOP pipeline:

```text
recordings/<recording_id>/manual_transcript.txt
```

Timed lines are preferred:

```text
00:00:01.000 --> 00:00:03.000 Open the target app.
00:00:03.500 --> 00:00:06.000 Submit the form.
```

Plain lines (no timestamps) are accepted and spaced four seconds apart.

Then run:

```bash
uv run screen-harness transcribe <recording_id>
uv run screen-harness sop ai-generate <recording_id>
uv run screen-harness redact scan <recording_id>
uv run screen-harness render <recording_id>
```

## Sensitive-info redaction

Use `redact_region(x, y, w, h, *, reason=None, duration=None)` to black-fill
any region containing passwords, tokens, PII, or other sensitive content. The
fill is applied at render time — `raw.mp4` is never mutated.

Run `scan_redactions()` (or `uv run screen-harness redact scan <id>`) to check
the transcript and timeline text for common sensitive patterns (emails, API
tokens, UUIDs).

Reusable helpers for a project's specific redaction patterns belong in
`agent-workspace/agent_helpers.py` — they are auto-loaded into every
`screen-harness -c` namespace.

## Version compatibility (consumer minimums)

This file is read natively by the following tools (LF Agentic AI Foundation
AGENTS.md spec, Feb 2026):

| Tool | Minimum version |
|------|----------------|
| Codex CLI | ≥ Feb 2026 release |
| GitHub Copilot Chat | current (with `useInstructionFiles` enabled) |
| Cursor | ≥ 2026.02 |
| Windsurf | ≥ 2026.02 |
| Amp | ≥ 2026.02 |
| Devin | current |

**Claude Code** reads `CLAUDE.md` (AGENTS.md support pending); see `CLAUDE.md`.

**Anthropic Skills** (on-demand invocation) use `SKILL.md`; see `SKILL.md`.
