# REF-2216: D2 sharingType Spike Findings

**Applies to:** SHR project
**Last updated:** 2026-05-11
**Last reviewed:** 2026-05-11
**Status:** Active
**Related:** SHR-2214 (revised D2 PRP)

---

## Question

Does `NSWindow.sharingType = NSWindowSharingNone` hide an AppKit window from
`ffmpeg -f avfoundation -i "N:none"` screen capture on this host
(macOS 25.4 / Darwin 25.4.0, FFmpeg 8.0.1)?

If yes, D2 HUD can be a top-level NSPanel covering the capture region without
being recorded. If no, the HUD must be drawn outside the capture region.

---

## Method

Spike scripts in `agent-workspace/d2_spike*.py`:

1. `d2_spike.py` — paints a 240×90 fully-red `NSPanel` at top-right of main
   screen with `sharingType = NSWindowSharingNone`. Records 3s with FFmpeg
   avfoundation. Samples panel-region pixels.
2. `d2_spike_control.py` — same but `sharingType = NSWindowSharingReadOnly`
   (default). If sharingType matters, this trial *should* show red pixels.
3. `d2_spike_v2.py` — single-process A/B trial with explicit AppKit activation
   policy (`NSApplicationActivationPolicyAccessory`) to ensure window
   actually renders.

---

## Results

| Trial | Panel-region avg RGB | Red pixel % | Notes |
|-------|----------------------|-------------|-------|
| v1 sharingType=.none | (132, 132, 132), max 243 | 0% | Identical to control |
| v1 control (ReadOnly) | (132, 132, 132), max 242 | 0% | Panel never rendered |
| v2 (A=none, B=ReadOnly) | — | — | FFmpeg pix_fmt negotiation failed under threaded NSApp |

The fact that the control trial produced the same pixels as the
`sharingType=.none` trial means **the NSPanel did not render into the
WindowServer surface at all** in our process context (likely because a
Python-launched-from-terminal process without `Info.plist` does not get a
regular window-server connection, even with `setActivationPolicy_(.accessory)`).
The spike therefore cannot distinguish "sharingType worked" from "panel
never appeared".

---

## External Evidence

Three independent reviewers (trinity-glm, trinity-deepseek, trinity-minimax),
plus the web sources cited below, converge on the same claim:

- `NSWindow.sharingType` is honoured by **ScreenCaptureKit** (macOS 12.3+)
  and by `CGWindowListCreateImage`.
- FFmpeg's `-f avfoundation` indev uses `AVCaptureScreenInput`, which
  historically captures the WindowServer framebuffer at a level below
  per-window `sharingType` hints.
- Apple Developer Forum thread 760234 ("App content protection failure")
  confirms `sharingType` does not affect framebuffer-level captures.
- Community evidence (Zoom Community thread on `NSWindowSharingNone`
  flickering with mac desktop screen capture) corroborates inconsistent
  honouring across capture paths.

---

## Decision

D2 v1 will **not** rely on `sharingType`. The HUD must be drawn **outside**
the capture region. A future PRP can migrate the capture backend to
ScreenCaptureKit, at which point a full-screen HUD becomes possible.

The spike scripts are left in `agent-workspace/` (gitignored as the rest of
that directory). They may be revived if FFmpeg adds explicit SCK backend
selection (`-capture_kit`-style flag) and we want to retest.

---

## Sources

- agents.md / Linux Foundation Agentic AI Foundation
- developer.apple.com/forums/thread/760234 — App content protection failure
- community.zoom.com — Flickering window in screen capture with NSWindowSharingNone
- FFmpeg 8.0.1 source — `libavdevice/avfoundation.m` still uses
  `AVCaptureScreenInput` (no SCK opt-in).

---

## Change History

| Date | Change | By |
|------|--------|----|
| 2026-05-11 | Initial findings + decision to abandon sharingType for D2 v1 | Claude Code |
