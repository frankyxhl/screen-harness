# Screen Harness

[![CI](https://github.com/frankyxhl/screen-harness/actions/workflows/ci.yml/badge.svg)](https://github.com/frankyxhl/screen-harness/actions/workflows/ci.yml)

Screen Harness is a CLI-first macOS tool for recording screen workflows and turning them into SOP videos and Markdown documents. It records an immutable `raw.mp4`, stores editable events in `timeline.json`, then renders an intro card, frosted-glass step overlays, highlight strokes, an outro/end card, and Markdown SOP from one timeline.

The MVP stays intentionally small: it proves the local recording → rendering loop before adding a daemon, global hotkeys, or cloud AI providers.

## What It Does

- Records the macOS screen with FFmpeg (AVFoundation).
- **Smart screen selection** (new in v0.2.0): auto-detects the right display via `screen=None` (main), `screen="display:2"` (1-indexed position), `screen=N` (raw AVFoundation index, validated to be a screen), or `app="Safari"` (resolves to the display containing Safari's front window). Refuses to record from the FaceTime camera even if it shares AV index 0. Run `screen-harness probe-screens` to list every active display.
- **Recording HUD overlay** (new in v0.2.0): when `region=` is set, a red `● REC HH:MM:SS` pill and 4-pt frame appear *outside* the capture region so the user sees what is being recorded — without bleeding into `raw.mp4`. Disable per call with `hud=False`. Suppressed automatically for full-screen captures.
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

Expected signals:

```text
screen capture: ok
render ffmpeg: ok
picked-screen-default: [N] Capture screen 0
```

Microphone can be `not detected`; recording works without microphone input.

**macOS extra** (recommended): `uv sync --extra macos` installs PyObjC (Quartz + Cocoa + AVFoundation). Without it, `probe_screens` cannot reliably distinguish cameras from displays in mixed-DPI multi-monitor setups, and the recording HUD subprocess won't render. The extra is dev-default; CI runners under `[dependency-groups.dev]` get it via the darwin guard.

Run `screen-harness probe-screens` (or `probe-screens --json`) to list every active display with its AVFoundation index, CGDirectDisplayID, pixel bounds, NSScreen point origin/size, backing scale, and whether it is the main display.

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
| `start_recording(name, *, screen=None, app=None, region=None, hud=True, capture_cursor=True, capture_mouse_clicks=True)` | Start FFmpeg AVFoundation capture. `screen` accepts an int AVFoundation index, `"display:N"` (1-indexed), `"auto:Safari"`, or `None` (auto-picks main display). `app="Safari"` resolves to the display containing Safari's front window. `region=(x, y, w, h)` crops to that screen rect (raises `RegionOutOfBoundsError` on overflow). `hud=True` (default when `region=` set) shows a red `● REC` pill + frame *outside* the crop. Writes a typed `picked_screen` block + `hud_active: bool` to `metadata.json`. |
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
start_recording("quick_demo", region=(200, 200, 1000, 700))
intro("This video demonstrates the quick demo", subtitle="A short Screen Harness example", countdown=5)
step("Open the target app", note="Prepare the workflow for recording.")
caption("Open the target app and prepare the workflow.")
wait(3)
outro("Thanks for watching", url="github.com/frankyxhl/screen-harness")
stop_recording()
render(template="training")
'
```

While this runs you should see the red `● REC HH:MM:SS` pill and a 4-pt red frame around the (200,200,1000,700) crop rect. They appear only on screen — `raw.mp4` is clean.

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
                            hud.py     — recording HUD overlay (D2)
                            screens.py — smart screen selection (D1)
examples/                 Runnable demo scripts
agent-workspace/          User-editable helper and domain-skill workspace
interaction-skills/       Reusable interaction notes
rules/                    Alfred planning and change records
scripts/                  Multi-agent docs sync (D3)
                            sync_agent_docs.py   — regenerate CLAUDE.md/copilot/SKILL.md
                            check_agent_docs.py  — CI drift detection
                            agent-docs-tails/    — per-tool tails authored alongside AGENTS.md
tests/                    Unit, BDD, and end-to-end tests
AGENTS.md                 Canonical source of always-on agent instructions (LF AAF spec)
CLAUDE.md                 Generated — read by Claude Code
.github/copilot-instructions.md
                          Generated — read by Copilot Chat (when opt-in enabled)
SKILL.md                  Generated — Anthropic Skill bundle entry point
```

## Development

```bash
uv run pytest -q
uv run --with pytest-cov pytest --cov=src/screen_harness --cov-report=term-missing -q
uv run python -m compileall -q src tests
af validate
```

Current test posture: **268 passing, 1 skipped** across unit, BDD-style, FFmpeg-backed end-to-end, and macOS-gated integration tests (the macOS-gated tests skip cleanly on Linux CI and on terminal-launched Python processes that cannot reach the WindowServer — see SHR-2216 for details).

## CI/CD

GitHub Actions runs on pull requests and pushes to `main`:

- `test`: Python `3.14` with `pytest` and `compileall`.
- `alfred`: validates `rules/` with `uvx --from fx-alfred af validate`.
- `agent-docs`: runs `scripts/check_agent_docs.py` to fail-fast if `AGENTS.md` (or any tail file) was edited without regenerating `CLAUDE.md` / `.github/copilot-instructions.md` / `SKILL.md`.
- `package`: builds source and wheel distributions with `uv build`, then uploads `dist/*` as the `screen-harness-dist` workflow artifact.

A separate **`release.yml`** workflow fires on `v*` tag pushes (see [RELEASING.md](RELEASING.md)) — runs tests, builds wheel+sdist, creates a GitHub Release, and publishes to PyPI via Trusted Publisher (OIDC; no API token).

## Use With Your AI Coding Assistant

This repo ships **agent instruction files** so coding assistants know how to drive `screen-harness` end-to-end without you copy-pasting docs into the chat. Pick the path for your tool.

### Path A — open the repo with your AI

Codex CLI, Cursor, Windsurf, Amp, Devin, GitHub Copilot Chat, and Claude Code all read instruction files from a repo automatically (subject to the per-tool caveats below). After cloning:

```bash
git clone https://github.com/frankyxhl/screen-harness
cd screen-harness
uv sync --extra macos
uv run screen-harness init
uv run screen-harness doctor
```

Then start a session in your AI tool from the `screen-harness` directory. You can say things like:

> "Use screen-harness to record me opening Safari and walking through the homepage of github.com, then render it as a training video."

> "Probe the screens and record a 30-second clip of the display where Slack is running. Crop to Slack's window."

> "Pick up where I left off in `recordings/safari_github_repo_demo_*` — re-render the SOP with my updated captions."

The AI will read `AGENTS.md` (canonical) plus the tool-specific stub (`CLAUDE.md`, `.github/copilot-instructions.md`, `SKILL.md`) and act on the helper API.

### Path B — install as a Claude Skill (Anthropic Skills bundle)

`SKILL.md` at the repo root is the Anthropic Skill bundle entry point with a tightened `name` + `description` frontmatter. To make Claude Code or Claude.ai discover it on-demand:

**Claude Code (CLI):**
```bash
# clone into a directory Claude Code scans for skills
git clone https://github.com/frankyxhl/screen-harness ~/.claude/skills/screen-harness
```
Restart Claude Code; the skill becomes invocable by name.

**Claude.ai web:**
Open https://claude.ai → Settings → **Skills** → **Upload skill** → point at the cloned `screen-harness` directory (or upload the bundle zip). Claude will pick it up across all your conversations.

Once installed, just say:
> "Use the screen-harness skill to record a 60-second screencast of my IDE while I refactor `foo.py`."

### Path C — use as a Python helper directly

`screen-harness` is also a CLI + Python helper. Install from PyPI — **always include the `[macos]` extra**; the base package has no runtime deps and `probe_screens` will raise `ScreenProbeError` without PyObjC (Quartz / Cocoa / AVFoundation):

```bash
uv add 'screen-harness[macos]'        # add to a uv project
# or
pipx install 'screen-harness[macos]'  # standalone CLI
# or
pip install 'screen-harness[macos]'   # plain pip
```

Then drive it from Python:
```python
from screen_harness.helpers import start_recording, stop_recording, wait
start_recording("demo", region=(200, 200, 1000, 700))
wait(10)
stop_recording()
```
or one-shot via the CLI:
```bash
uv run screen-harness -c '
start_recording("demo", region=(200, 200, 1000, 700))
wait(10)
stop_recording()
'
```

### Which file each tool reads

| Tool | Reads file | Minimum version |
|------|-----------|----------------|
| Codex CLI | `AGENTS.md` | ≥ Feb 2026 release |
| GitHub Copilot Chat | `.github/copilot-instructions.md` | current (opt-in — see below) |
| Cursor | `AGENTS.md` | ≥ 2026.02 |
| Windsurf | `AGENTS.md` | ≥ 2026.02 |
| Amp | `AGENTS.md` | ≥ 2026.02 |
| Devin | `AGENTS.md` | current |
| Claude Code | `CLAUDE.md` | current (AGENTS.md support pending) |
| Anthropic Skills (on-demand) | `SKILL.md` | current |

**Copilot opt-in caveat:** `.github/copilot-instructions.md` is read by GitHub Copilot Chat *only* when the `github.copilot.chat.codeGeneration.useInstructionFiles` setting is enabled. This is per-user and off by default — enable it in VS Code settings or at github.com.

### Maintaining the instruction files

`AGENTS.md` is the **canonical source**. `CLAUDE.md`, `.github/copilot-instructions.md`, and `SKILL.md` are *generated* from `AGENTS.md` + tail files under `scripts/agent-docs-tails/`. Editing those generated files directly will be detected by CI (the `agent-docs` job) and fail the build. To make an authoritative change:

```bash
# edit AGENTS.md or scripts/agent-docs-tails/<tool>.md
python scripts/sync_agent_docs.py
git add AGENTS.md scripts/agent-docs-tails/ CLAUDE.md .github/copilot-instructions.md SKILL.md
git commit
```
