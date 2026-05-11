# Screen Harness — Agent Instructions

## When to use this project

Use Screen Harness to record macOS screen workflows and turn them into SOP videos.

## Install

```bash
uv sync
uv run screen-harness init
uv run screen-harness doctor
```

## Recording script shape

Every recording is a single Python script via `screen-harness -c '<python>'`.

## Helper API

| Helper | What it does |
|--------|--------------|
| `start_recording(name)` | Begin capture. |
| `stop_recording()` | End capture. |

## AI SOP generation

Drop `manual_transcript.txt` beside the recording and run `sop ai-generate`.

## Sensitive-info redaction

Use `redact_region(x, y, w, h)` to black-fill sensitive content at render time.

## Version compatibility (consumer minimums)

| Tool | Minimum version |
|------|----------------|
| Codex CLI | ≥ Feb 2026 release |
| GitHub Copilot Chat | current (with `useInstructionFiles` enabled) |
| Cursor | ≥ 2026.02 |
| Windsurf | ≥ 2026.02 |
| Amp | ≥ 2026.02 |
| Devin | current |
