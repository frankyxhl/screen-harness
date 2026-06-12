# Screen Harness Install & Troubleshooting

Quick install lives in the [README](README.md#install). This file covers the
setup details and the failure modes `doctor` can surface. Usage (recording
scripts, SOP generation) lives in the README and `SKILL.md`.

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

Two different FFmpeg capabilities are needed:

- **Capture** uses the default `ffmpeg` on PATH and needs the `avfoundation`
  input device. Homebrew's regular `ffmpeg` formula provides this.
- **Render** burns ASS subtitles and draws highlight boxes, which needs the
  `subtitles` (or `ass`) **and** `drawbox` filters. Homebrew's regular
  `ffmpeg` 8.x **no longer bundles libass**, so it cannot render — install
  the keg-only `ffmpeg-full` formula alongside it:

```bash
brew install ffmpeg ffmpeg-full
```

The renderer automatically prefers `/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg`
when it exists. To use a different libass-enabled build:

```bash
SCREEN_HARNESS_FFMPEG=/path/to/ffmpeg screen-harness render <recording_id>
```

`screen-harness doctor` reports both capabilities separately: `screen
capture: ok` covers the capture binary, `render ffmpeg: ok` covers the
filter set.

## macOS Permissions

Screen Recording permission must be granted to **whichever process launches
ffmpeg** (Terminal, iTerm, your agent runtime …) via System Settings →
Privacy & Security → Screen & System Audio Recording. macOS prompts on first
capture; recordings made while the consent dialog is up will include the
dialog itself.

Verify with:

```bash
screen-harness doctor
```

Expected signals:

- `screen capture: ok`
- `render ffmpeg: ok`
- microphone may be `not detected`; microphone recording is optional.

If `probe_screens` raises `ScreenProbeError` mentioning Screen Recording
permission, FFmpeg is enumerating zero screen devices while displays exist —
grant the permission and retry. Without the `[macos]` PyObjC extra,
`probe_screens` raises immediately; install with `uv sync --extra macos` or
`pip install 'screen-harness[macos]'`.
