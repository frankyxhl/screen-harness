# PRP-2213: Smart Screen Selection

**Applies to:** SHR project
**Last updated:** 2026-05-11
**Last reviewed:** 2026-05-11
**Status:** Approved
**Revision:** R2 — revised after R1 three-model parallel review
**Approved by:** Trinity R2 — glm PASS 9.05, deepseek PASS 9.3, minimax PASS 9.2 (3/3 unanimous, all R1 blockers closed, zero new blockers)
**Related:** D1 in SHR-2212

---

## What Is It?

A start-of-recording subsystem that (a) enumerates AVFoundation video devices
every launch, (b) refuses to record from a camera, (c) can auto-resolve "the
screen the target app is on" so an AI agent only has to say
`screen="auto:Safari"`, and (d) writes a fully-typed picked-screen record into
`metadata.json`.

---

## Problem

`recorder.build_screen_record_command` (src/screen_harness/recorder.py:13)
defaults to `-i 0:none`. On most macOS hosts AVFoundation index `0` is the
FaceTime camera — the user has observed Screen Harness recording the webcam
instead of the screen. On multi-display setups, multiple `Capture screen N`
devices exist and a hardcoded index records the wrong monitor.
`admin.list_avfoundation_devices` already returns the right metadata but
`start_recording` does not consume it.

R1 reviewers (deepseek, glm, minimax all FAIL) flagged two unanimous blockers:

- **Locale-fragile detection** — gating on the literal substring `"screen"`
  in device names rejects every screen on non-English macOS (zh "捕捉屏幕",
  ja "画面収録", es "Captura de pantalla", fr "Capture d'écran").
- **AV-index ↔ CGDirectDisplayID mapping was hand-waved** — the suffix in
  `Capture screen 0` is AVFoundation's own counter, not a `CGDirectDisplayID`.
  Without an explicit, verified mapping, `auto:Safari` cannot reliably map a
  window's screen to an AV index on multi-display setups.

R2 fixes both: detection becomes structural, and the AV↔display mapping is
specified as an algorithm with an integration-test invariant.

---

## Scope

**In scope:**

- New module `src/screen_harness/screens.py`:

  ```python
  @dataclass(frozen=True)
  class ScreenDevice:
      av_index: int                         # FFmpeg avfoundation `-i N`
      av_name: str                          # raw device name (locale-dep)
      display_id: int                       # CGDirectDisplayID
      bounds: tuple[int, int, int, int]     # x, y, w, h global pixel coords
      is_main: bool                         # display_id == CGMainDisplayID()
      backing_scale: float                  # Retina factor for this display

  @dataclass(frozen=True)
  class PickedScreen:
      device: ScreenDevice
      reason: str   # "explicit-int:0" | "auto-front-app:Safari"
                    # | "default-main" | "display-pos:1"
                    # | "auto-no-app-no-front-window:fallback-main"

  def probe_screens(*, ffmpeg=...) -> list[ScreenDevice]: ...
  def resolve_screen(spec, *, app=None, ffmpeg=...) -> PickedScreen: ...
  ```

- **Structural detection** (not name-based):
  `admin.parse_avfoundation_devices` already splits output into a `video`
  list parsed from the "AVFoundation video devices:" section header. FFmpeg
  emits camera devices first, then screen devices, with a separator line.
  We extend the parser to track the *sub-section* heuristic used by FFmpeg
  itself: a video device is a *screen* iff its enumeration position is
  `>= camera_count`, where `camera_count = N_video_devices - N_active_displays`
  and `N_active_displays = len(CGGetActiveDisplayList())` via Quartz. This
  is locale-independent: it uses only counts, not names.

  A defensive secondary check: AVFoundation video devices that *are* screens
  are reported by FFmpeg with the device flags pattern `Capture screen N`
  on English locale and the localized equivalent elsewhere, but the
  *display count* invariant always holds. The parser asserts
  `N_video_devices >= N_active_displays`; if it fails (impossible per Apple
  docs, but defensive) it raises `ScreenProbeError` with diagnostic.

- **AV-index ↔ CGDirectDisplayID algorithm** (with verified invariant):

  1. Call `Quartz.CGGetActiveDisplayList(maxDisplays=16)` → list of
     `CGDirectDisplayID` in WindowServer-active order.
  2. Call `parse_avfoundation_devices` → split into camera + screen sections.
  3. Bind the *k*-th screen device (AV index = `camera_count + k`) to the
     *k*-th `CGDirectDisplayID`.
  4. For each binding, populate `bounds` from `Quartz.CGDisplayBounds(id)`
     and `backing_scale` from `NSScreen.backingScaleFactor`.

  **Verification invariant** (asserted in macos-gated integration test): for
  every `ScreenDevice`, recording a 0.3s clip of *only that device* and
  comparing the average colour of a paired AppKit-drawn coloured square
  (via PyObjC on the matched `NSScreen`) shows the expected colour. The
  invariant either passes (binding correct) or fails loudly with which
  device mis-mapped. **No assumption — the test verifies the binding on
  every CI run that has a Mac runner.**

- **`resolve_screen` semantics** (R1 advisory items, now in scope):

  | `spec` | `app` | Behavior |
  |---|---|---|
  | `None` | `None` | Pick main display; reason `default-main`. |
  | `None` | `"Safari"` (app running, has front window) | Get window bounds via AppleScript; pick screen whose `bounds` contain the window centre; reason `auto-front-app:Safari`. |
  | `None` | `"Safari"` (app not running OR no front window) | Log warning, fall back to main; reason `auto-no-app-no-front-window:fallback-main`. |
  | `int n` | * | Validate `0 <= n < len(devices)` AND `devices[n]` is a screen; raise `ValueError` with helpful message if `n` is a camera. Reason `explicit-int:n`. |
  | `"display:k"` (1-indexed) | * | Pick the *k*-th `ScreenDevice` (k=1 = main if `is_main`); raise on out-of-range. Reason `display-pos:k`. |

  CLI help text spells out the 1-indexed vs 0-indexed distinction loudly.

- **Camera-rejection gate** in `build_screen_record_command`: takes a
  `ScreenDevice` (not a raw int) and panics if `device.display_id == 0`
  (sentinel for "no display"). Direct `int` invocation paths go through
  `resolve_screen` first.

- New CLI: `screen-harness probe-screens [--json]` — prints inventory + main
  marker + bounds.

- `start_recording` always calls `probe_screens()` and logs to stdout
  (`Available screens:` block) **on the first launch of a process** (cached
  in `_STATE` for subsequent calls in the same Python session — addresses
  R1 minimax advisory about spam).

- `metadata.json["picked_screen"]` schema documented in
  `src/screen_harness/metadata.py` with a JSON-schema fixture under
  `tests/fixtures/picked_screen.schema.json` (tested round-trip).

- `doctor` output adds `picked-screen-default:` line showing what
  `resolve_screen(None)` would choose.

**Out of scope:**

- Window-only capture (the existing `region=` covers it).
- Cross-platform — macOS only.
- A GUI picker.

---

## Tests

- Unit: `probe_screens` parses fixture AVFoundation listings (en, zh, ja, es,
  fr locales — all real-world examples checked in under
  `tests/fixtures/avfoundation_devices/`) → expected `ScreenDevice` list.
  Locale-independent.
- Unit: `resolve_screen` table-driven for every cell in the spec×app matrix
  above, including:
  - camera-rejection (`int=0` when 0 is a camera) → `ValueError`.
  - `auto:Safari` when Safari not running → warning + main fallback.
  - `display:99` → `IndexError`.
- Unit: JSON-schema round-trip for `picked_screen`.
- Macos-gated integration:
  - Probe real host; assert at least one screen, no cameras returned.
  - **AV↔CGDirectDisplayID invariant test** as described above (paired
    coloured-square recording).
- Regression: existing recorder tests still pass; mock `resolve_screen` to a
  fixed `ScreenDevice` so they remain hermetic.

---

## Risks

- **AppleScript denial** (Automation permission): catch `osascript` non-zero,
  log clearly, fall back to main display, don't crash.
- **PyObjC absent**: import lazily; degrade to "main display only" mode and
  log a one-line install hint. Without PyObjC the `Quartz` calls are
  unavailable so AV↔display binding is best-effort (first screen device =
  main display); skip the invariant test on such hosts.
- **AVFoundation enumeration order change** in a future macOS: the
  invariant test catches it on the next CI run. Caught early, not in prod.
- **`CGGetActiveDisplayList` return order vs FFmpeg order**: per Apple docs
  the active list returns the main display first followed by mirrored
  copies in the order they appear in the Displays preference pane. The
  invariant test is the contract; if Apple changes ordering, the test
  fails loudly.

---

## Acceptance

- On a host where AVFoundation index 0 is the FaceTime camera, running
  `screen-harness -c 'start_recording("t"); stop_recording()'` records from
  a screen device, never the camera.
- `screen-harness probe-screens` lists every screen with `display_id`,
  `bounds`, `is_main`, exit 0.
- `start_recording(..., screen="auto:Safari")` records from the display
  whose bounds contain Safari's front window centre point. Verified by the
  macos-gated invariant test.
- `start_recording(..., screen="auto:NotRunningApp")` falls back to main
  with a warning log line; recording proceeds.
- `metadata.json["picked_screen"]` validates against
  `tests/fixtures/picked_screen.schema.json`.
- Unit tests pass on every locale fixture (en/zh/ja/es/fr).

---

## Change History

| Date | Change | By |
|------|--------|----|
| 2026-05-11 | R1 — Initial proposal | Claude Code |
| 2026-05-11 | R2 — Address R1 blockers: structural locale-independent detection (count-based); explicit AV↔CGDirectDisplayID algorithm + invariant test; full resolve_screen behavior matrix; picked_screen JSON schema; locale fixture suite | Claude Code |
