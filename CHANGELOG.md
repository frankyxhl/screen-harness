# Changelog

All notable changes to Screen Harness are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
(pre-1.0: minor bumps may carry behavior changes).

## [0.3.0] - 2026-06-14

### Added

- **`timeline.json` load validation.** `Timeline.load()` now validates the
  document structure and raises `TimelineError` with a message naming the
  offending field (e.g. `events[0] (evt_001) needs a numeric 't'`). Hand-edited
  timelines — a documented core workflow — fail fast at load instead of as an
  opaque `KeyError` mid-render. The CLI prints a one-line error, no traceback.

### Fixed

- **Local timezone.** All persisted timestamps (timeline `created_at`,
  `recording_id` slugs, metadata `updated_at`/`stopped_at`/`rendered_at`, SOP
  `generated_at`, redaction/transcript `created_at`) now use the machine's
  local timezone instead of a hardcoded `Asia/Tokyo`. Existing `+09:00` data
  stays parseable; only newly written values change.
- **Render frame rate.** `render()` no longer silently defaults to 30 fps when
  the rate is unresolvable — intro/outro card clips would mis-time against a
  24/60 fps raw clip. The rate is recovered from a fresh `ffprobe` when
  metadata lacks it; required only when card clips are actually generated, so
  main-only renders of older recordings still proceed.
- PyObjC screen probing now fails closed across AVFoundation as well (no
  silent fallback to AVFoundation index 0 when permission is missing).

### Documentation

- Consolidated install docs and documented the `ffmpeg-full` requirement —
  Homebrew's regular `ffmpeg` 8.x no longer bundles libass, so rendering needs
  the keg-only `ffmpeg-full` formula (`brew install ffmpeg ffmpeg-full`).

### Internal

- Split the 1100-line `helpers.py` into five focused modules (`runtime`,
  `recording`, `rendering`, `hud_supervisor`, `probing`); the public helper
  facade and `-c` script namespace are unchanged.
- CI now gates on `ruff`, `mypy`, a Python 3.11–3.14 matrix, and a real
  `macos-latest` runner exercising the AVFoundation/Quartz path.

## [0.2.0] - 2026-05-12

- Professional SOP render templates (intro card, numbered step cards, outro),
  AI SOP generation from manual transcripts, sensitive-info redaction, and the
  agent-facing helper API. See the git history for details.

## [0.1.0]

- Initial MVP: CLI-first screen recording with `timeline.json`, ffmpeg
  capture + render, and Markdown SOP output.

[0.3.0]: https://github.com/frankyxhl/screen-harness/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/frankyxhl/screen-harness/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/frankyxhl/screen-harness/releases/tag/v0.1.0
