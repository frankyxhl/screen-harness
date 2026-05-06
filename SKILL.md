---
name: screen-harness
description: |
  Record macOS screen workflows and turn them into SOP videos and Markdown
  documents. Captures an immutable raw.mp4 + editable timeline.json, then
  renders an intro card, frosted-glass step overlays, teal highlight strokes,
  and an outro card with the project URL — all from one Python script.
  Use this skill when the user asks for a screen recording, an SOP video,
  a tutorial-style walkthrough, or wants to wire up Screen Harness helpers.
---

# Screen Harness

CLI-first macOS recording → SOP rendering tool. The orchestration entry
point is `screen-harness -c '<python>'`, which exec's an inline script with
all helpers pre-imported. There is no daemon, no global hotkey — every
recording is one Python script you can re-run.

## When to invoke this skill

- The user wants to record a workflow on macOS (a process tour, a bug
  reproduction, a feature demo) and end up with a polished video + Markdown.
- The user mentions Screen Harness, `screen-harness`, `expense_sop.py`,
  `timeline.json`, "training template", or asks about recording into the
  `recordings/` directory.
- The user wants to add an intro, step cards, callouts, or a branded outro
  to an existing recording without re-shooting.

Do **not** use this skill for live transcription / streaming, multi-display
recording, or anything that requires a persistent background daemon — those
are explicitly out of MVP scope.

## Install (one-time per machine)

```bash
uv sync                              # install dependencies into .venv
uv run screen-harness init           # create recordings/, agent-workspace/, etc.
uv run screen-harness doctor         # verify ffmpeg + AVFoundation
```

`doctor` should print at least:

```text
screen capture: ok
render ffmpeg: ok
```

Microphone may show as `not detected` — that's fine for the MVP. Recording
needs Screen Recording permission for whichever process runs `ffmpeg`
(Terminal, iTerm, Claude Code …) — grant it in System Settings → Privacy
& Security → Screen & System Audio Recording the first time.

## The shape of a recording script

Every Screen Harness recording is a single Python program executed via
`screen-harness -c '<...>'`. All helpers below are pre-imported into the
script's namespace.

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

…or inline (for quick experiments):

```bash
uv run screen-harness -c '
start_recording("smoke")
intro("Smoke", countdown=3)
step("It works")
wait(2)
outro(url="github.com/frankyxhl/screen-harness", duration=3.0)
stop_recording()
render(template="training")
'
```

## Helper reference

| Helper | What it does |
|--------|--------------|
| `start_recording(name, *, region=None, capture_cursor=True, capture_mouse_clicks=True, screen=None, mic=None)` | Begin AVFoundation capture. `region=(x, y, w, h)` crops to a screen rect (e.g. a single app window). |
| `stop_recording()` | End capture, finalize `metadata.json`. |
| `wait(seconds)` / `wait_for_user(msg)` | Pace the script. |
| `intro(title, *, subtitle=None, countdown=5)` | Pre-roll intro card on charcoal background. |
| `chapter(title)` | Logical chapter marker (currently informational only). |
| `step(title, *, note=None, number=None)` | A frosted-glass step card overlay during this beat. |
| `caption(text, *, duration=None)` | Caption track entry → `sop.srt`. |
| `click(x, y, *, label=None)` | Red dot click marker. |
| `highlight_region(x, y, w, h, *, text=None, duration=3.0, color="0x00ADB5@0.85", thickness=6)` | Teal stroke around a region. Coordinates are in the cropped frame, not the full screen. |
| `redact_region(x, y, w, h, *, reason=None, duration=None)` | Black-fill sensitive content. |
| `outro(title="Thanks for watching", *, subtitle=None, url=None, duration=4.0)` | Held end card with project URL. |
| `render(*, template="training" | "debug")` | Build SOP assets + `final.mp4`. |
| `transcribe()` / `generate_ai_sop()` / `scan_redactions()` | Manual-transcript-driven SOP + redaction scan. |

## Window-only recording (no Dock, no menu bar)

To capture only one app's window:

1. Move/size the window deterministically with AppleScript:
   ```python
   import subprocess
   subprocess.run(["osascript", "-e",
       'tell application "Safari" to set bounds of front window to {0,0,1920,1080}'],
       check=False)
   ```
2. Read the window's *actual* bounds (macOS will clamp under the menu bar):
   ```python
   bounds = subprocess.run(
       ["osascript", "-e", 'tell application "Safari" to get bounds of front window'],
       capture_output=True, text=True).stdout.strip()
   x1, y1, x2, y2 = (int(p.strip()) for p in bounds.split(","))
   region = (x1, y1, x2 - x1, y2 - y1)
   ```
3. Pass it as `start_recording(..., region=region)`.
4. Author every `highlight_region` / `click` coordinate in the *cropped*
   frame coordinate system (`(0, 0)` = the window's top-left).

`examples/expense_sop.py` is a complete working reference for this pattern.

## What gets produced

Inside `recordings/<recording_id>/`:

- `raw.mp4` — immutable original capture
- `timeline.json` — editable event list (steps, captions, highlights, intro, outro)
- `sop.srt` / `sop.ass` / `sop.md` — caption assets generated from the timeline
- `intro.ass` / `intro-source.mp4` / `intro.mp4` — intro card pieces
- `main.mp4` — the burned-in main recording (subtitles + frosted panel + highlights)
- `outro.ass` / `outro-source.mp4` / `outro.mp4` — end-card pieces
- `final.mp4` — concatenated intro + main + outro
- `metadata.json` — canvas size, region, ffmpeg version, status, timestamps
- `ffmpeg.log` — capture stderr/stdout

Re-render anytime after editing `timeline.json`:

```bash
uv run screen-harness render <recording_id> --template training
```

## Visual system

Color Hunt's "DevDark" palette, applied consistently:

- `#222831` charcoal — intro/outro background
- `#393E46` graphite — wordmarks, secondary text
- `#00ADB5` teal — single accent (countdown, step number, highlight strokes, outro URL)
- `#EEEEEE` off-white — primary foreground; also tint of the frosted step card

The step card is a fixed `1180×150` rectangle anchored at the bottom-left.
Under the hood, FFmpeg `split → crop → boxblur=24 → tint #EEEEEE@0.55 →
overlay` paints the frosted glass; ASS `\an7\pos(...)` keeps the text
fixed-position so the panel never breathes with text length.

## Manual transcript format

Used by `transcribe` / `sop ai-generate` when there's no audio capture. Drop
`recordings/<id>/manual_transcript.txt`:

```text
00:00:01.000 --> 00:00:03.000 Open the target app.
00:00:03.500 --> 00:00:06.000 Submit the form.
```

Plain lines (no timestamps) are also accepted and spaced four seconds apart.

## Common pitfalls

- **Wrong rectangle coordinates.** If the recording uses `region=`, every
  highlight is in the *cropped* coordinate system. Forgetting to subtract
  the crop origin is the #1 cause of off-target callouts.
- **Window not maximized.** The Safari demo uses AppleScript to force a
  known size; without that, GitHub's centered max-width layout will sit at
  unpredictable x-coordinates. Always pin the window before recording.
- **`do JavaScript` silently fails** unless Safari → Develop menu → "Allow
  JavaScript from Apple Events" is enabled. Affects `scroll_safari` and
  similar helpers in the demo.
- **Local FFmpeg is `ffmpeg-full`.** Recording uses the system `ffmpeg`,
  but rendering needs ASS/`subtitles` filter support. The runtime auto-
  selects `/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg` when present; override
  with `SCREEN_HARNESS_FFMPEG=/path/to/ffmpeg` if needed.
- **No audio passthrough yet.** Concatenated `final.mp4` is video-only —
  audio passthrough is on the roadmap, not in MVP.

## Out of scope (do not propose)

- Background daemons or global hotkeys.
- Cloud transcription / cloud LLM SOP generation (manual transcript only).
- Multi-display capture, virtual webcams, or real-time streaming.
- Editing `raw.mp4` — it is immutable by design; edit `timeline.json` and
  re-render instead.

## Putting reusable knowledge somewhere durable

- Put **executable helpers** (project-specific Python utilities) in
  `agent-workspace/agent_helpers.py` — they are auto-loaded into every
  `screen-harness -c` script's namespace.
- Put **process knowledge** (how a particular flow should be recorded) in
  `agent-workspace/domain-skills/<system>/<flow>.md`.

## Verification commands

```bash
uv run pytest -q                                              # unit + BDD + e2e
uv run --with pytest-cov pytest --cov=src/screen_harness -q   # coverage
uv run python -m compileall -q src tests                      # syntax sanity
af validate                                                   # rules/ structure
```
