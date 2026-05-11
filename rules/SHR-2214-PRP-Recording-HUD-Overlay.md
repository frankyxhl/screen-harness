# PRP-2214: Recording HUD Overlay (REC dot + capture-region frame)

**Applies to:** SHR project
**Last updated:** 2026-05-11
**Last reviewed:** 2026-05-11
**Status:** Implemented
**Revision:** R2 — re-architected after spike SHR-2216
**Approved by:** Trinity R2 — glm PASS 9.33, deepseek PASS 9.0, minimax PASS 9.3 (3/3 unanimous)
**Related:** D2 in SHR-2212, depends on PRP-2213 (PyObjC dependency),
spike findings in SHR-2216

---

## What Is It?

A transparent, click-through, always-on-top macOS overlay shown while
`start_recording` is active. It draws **outside the capture region only**, so
no `sharingType` magic is required to keep it out of the recording. The HUD
shows:

- A red "● REC HH:MM:SS" pill placed at the nearest safe edge **outside**
  `region=`.
- A red 4-px outline drawn around the **outer perimeter** of `region=`
  (the stroke sits 4 px outside the crop rect, so it is *adjacent to* but
  not inside the recorded pixels).

**When the recording covers the whole screen** (no `region=`, or `region=`
equals the picked screen's bounds), the HUD is **suppressed** and a clear
warning is printed to stdout: "Full-screen recording — HUD disabled (cannot
guarantee zero capture); enable HUD by passing region=".

This avoids the unverified `sharingType=.none` claim (see SHR-2216 spike
findings) at the cost of one constraint: full-screen recording has no
visual recording indicator. A future PRP can lift this by migrating capture
to ScreenCaptureKit.

---

## Problem

Currently the user has no visible signal that recording is in progress, and
no visible signal of what region is being captured. Burning a red dot into
the recorded frames is unacceptable — it would appear in the final SOP video.

R1 reviewers (deepseek, glm, minimax all FAIL) unanimously rejected the
original sharingType-based architecture. Spike SHR-2216 confirms the
empirical risk is real-enough to architect around it.

---

## Scope

**In scope:**

- New module `src/screen_harness/hud.py` with two `NSPanel` subclasses:
  - `RecPillPanel` — red rounded rectangle, white text "● REC HH:MM:SS",
    SF Mono 14pt. Auto-positioned at the nearest safe corner *outside* the
    crop rect (priority: bottom-right > top-right > bottom-left > top-left;
    falls back to the screen edge closest to the crop rect).
  - `RegionFramePanel` — four thin (4-px wide × W-tall, or H-wide × 4-px
    tall) borderless NSPanels arranged as a stroke 4 px outside the crop
    rect. Four panels instead of one transparent panel-with-outline avoids
    the transparent-panel-with-frame coordinate bugs reviewers warned about.
- Both panels configured:
  - `level = NSStatusWindowLevel` (above floating, below screen-saver).
  - `ignoresMouseEvents = True` (click-through).
  - `opaque = True` (we are drawing only on solid pixels — no transparency
    coord-system headaches).
  - `collectionBehavior |= CanJoinAllSpaces | Stationary | FullScreenAuxiliary`.
- Coordinate transform spelled out:
  - `region=` is in **picked-screen pixels, top-left origin** (matches the
    `crop=W:H:X:Y` ffmpeg filter argument).
  - `NSPanel.setFrame_display_` uses **AppKit points, bottom-left origin**
    on the *global* AppKit coordinate space (where each screen's frame is
    pre-positioned).
  - Conversion: `appkit_x = screen.frame.origin.x + region_x / backing_scale`
    and `appkit_y = screen.frame.origin.y + (screen.frame.height -
    (region_y + region_h) / backing_scale)`.
  - Unit-tested with golden fixtures for: 1×1080p main, 2×2880×1800 @2x
    Retina main, side-by-side 1080p + Retina dual screen.
- HUD runs in a child process `python -m screen_harness.hud`:
  - Parent → child via JSON-on-stdin: `{"cmd":"start", "screen":<…>, "region":<…>}`
    and `{"cmd":"stop"}`.
  - Child runs `NSApp.run()` on its main thread.
  - **Parent-death watcher**: child reads stdin in a poller thread; an EOF
    on stdin (pipe closed because parent died) calls `NSApp.terminate_`. No
    `NOTE_EXIT`/kqueue trickery — stdin EOF is the canonical idiom on
    Unix-like systems and works regardless of entitlements.
- `start_recording` kwarg `hud: bool = True`. Default on when `region=` is
  set; default to printing the "HUD disabled" warning otherwise.
- `stop_recording` tears HUD down (closes stdin → child exits) on every
  path including KeyboardInterrupt.
- HUD subprocess startup latency budget: ≤ 300 ms. Teardown budget:
  ≤ 200 ms (stdin close → child sees EOF → NSApp.terminate). Both asserted
  in macos-gated integration tests.
- A **negative-space selftest** is the hard contract: record 3 s with HUD
  on, then assert that the HUD region (computed for the picked screen)
  outside the crop rect is whatever it is, but **the crop region itself
  contains no HUD-coloured pixels** (because the HUD is outside it; if any
  red pixel appears inside `region`, ffmpeg dimensioning is wrong).

**Out of scope:**

- A stop button on the HUD.
- Audio level meter.
- HUD when recording covers the whole screen (the SCK-backend PRP will lift
  this).
- HUD that follows a moving region.

---

## Tests

- Unit: HUD coordinate transform table (Retina, dual-screen).
- Unit: REC pill positioning algorithm — given a screen rect + a crop rect,
  returns the right anchor corner.
- Unit: JSON command parser + state machine (no AppKit needed).
- Macos-gated integration:
  - Spawn HUD subprocess; send `start` then `stop`; assert clean exit
    within 200 ms.
  - Crash parent; assert HUD subprocess exits within 1 s (via EOF on its
    stdin reader).
  - Selftest: record with HUD on at a sub-screen region; assert
    `final.mp4` crop contains no red pixels.
- BDD: `start_recording(..., region=(x,y,w,h), hud=True)` followed by
  `stop_recording()` produces final video unchanged from `hud=False`
  control run (byte-identical to within encoder noise — compare frame
  hashes outside the HUD bands, not whole-file).

---

## Risks

- **HUD panels at status-window level can still be hidden by other
  full-screen apps**: documented constraint; if the user is recording while
  another app is in full-screen on the same Space, the HUD does not show.
  Mitigation: `CollectionBehavior` flags above; if it still fails for an
  app, the warning is the same as the full-screen case.
- **Multi-display crop region**: if `region=` straddles two displays, the
  HUD subsystem picks the picked-screen and ignores spillover. Documented.
- **Child process zombie**: the EOF-on-stdin watcher is the canonical
  shutdown signal; combined with `start_new_session=True` parent process
  termination cascades to the child via SIGPIPE if it ever writes back.

---

## Acceptance

- Start recording with `region=(100,100,800,600)` → red REC pill appears
  outside the rect; red 4-px frame appears around the outer perimeter; both
  disappear within 200 ms of `stop_recording()`.
- `final.mp4` cropped region contains zero red pixels (selftest passes).
- Aborting harness (Ctrl-C) tears down both FFmpeg and HUD subprocess.
- Start recording with no `region=` → no HUD, single stdout warning line.
- `start_recording(..., region=…, hud=False)` skips HUD entirely.
- Unit tests for coordinate transform pass on Retina + dual-screen fixtures.

---

## Change History

| Date | Change | By |
|------|--------|----|
| 2026-05-11 | R1 — Initial proposal (sharingType-based, REJECTED by 3 reviewers) | Claude Code |
| 2026-05-11 | R2 — Re-architect after SHR-2216 spike: HUD outside crop region only, no sharingType dependency; full coordinate transform spec; stdin-EOF parent-death watcher (replaces NOTE_EXIT mis-spec); negative-space selftest as hard contract | Claude Code |
