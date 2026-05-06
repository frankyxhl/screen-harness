# REF-2205: Milestone 0 FFmpeg Findings

**Applies to:** SHR project
**Last updated:** 2026-05-06
**Last reviewed:** 2026-05-06
**Status:** Active

---

## What Is It?

A record of local FFmpeg capabilities and failure modes discovered during Milestone 0. These findings guide `doctor`, recorder defaults, and renderer selection for the first Screen Harness implementation.

---

## Content


## Environment

- Default FFmpeg: `/opt/homebrew/bin/ffmpeg`
- Default FFmpeg version: `8.0.1`
- Render-capable FFmpeg: `/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg`
- `ffmpeg-full` version: `8.0.1`
- Python used by `uv run`: `3.12.13`


## Device Discovery

Command:

```bash
ffmpeg -hide_banner -f avfoundation -list_devices true -i ""
```

Observed:

- Video devices include `0:Capture screen 0`.
- Audio devices are not listed.
- Probe exits non-zero with `Error opening input files: Input/output error`.

Interpretation:

- Main-display screen capture is available.
- Microphone capture should be optional in M0/M1 unless a later probe finds an audio device.
- `doctor` should report the non-zero probe as a note, not a total failure, when video devices were parsed successfully.


## Renderer Discovery

Default `/opt/homebrew/bin/ffmpeg` has:

- `drawbox`
- no `subtitles`
- no `ass`
- no `drawtext`
- no `libass`, `fontconfig`, or `freetype` build flags

`/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg` has:

- `subtitles`
- `ass`
- `drawtext`
- `drawbox`
- `overlay`
- `--enable-libass`
- `--enable-libfontconfig`
- `--enable-libfreetype`

Decision:

- Use default `ffmpeg` for AVFoundation capture.
- Prefer `ffmpeg-full` for ASS burn-in rendering when available.
- Allow `SCREEN_HARNESS_FFMPEG` to override the render binary.


## Verification Results

- Unit tests: `uv run pytest -q` → `10 passed`.
- Doctor: `uv run screen-harness doctor` reports screen capture ok, microphone not detected, and render FFmpeg ok via `ffmpeg-full`.
- Render smoke: `uv run screen-harness spike render-smoke .screen-harness-spike` created:
  - `.screen-harness-spike/raw.mp4`
  - `.screen-harness-spike/sop.ass`
  - `.screen-harness-spike/final.mp4`
- Render smoke output probe:
  - `640x360`
  - `30/1` fps
  - `3.000000` seconds
- Render regression smoke after post-review hardening also completed successfully under `.screen-harness-spike/render-regression/`.
- Screen recording smoke:
  - `uv run screen-harness spike record .screen-harness-spike/screen-30s.mp4 30`
  - output probe: `1920x1080`, `30/1` fps, `29.933333` seconds


## Known Warnings

- AVFoundation logs `Configuration of video device failed, falling back to default`.
- AVFoundation reports requested input pixel format `yuv420p` is unsupported and overrides to `uyvy422`.
- Capture still succeeds and the encoded output is `yuv420p`.
- Microphone device discovery is currently unavailable in the default probe.

---

## Change History

| Date       | Change                                                 | By    |
|------------|--------------------------------------------------------|-------|
| 2026-05-06 | Initial version                                        | —     |
| 2026-05-06 | Added Milestone 0 FFmpeg/device/render findings        | Codex |
| 2026-05-06 | Updated unit-test count and render regression evidence | Codex |
