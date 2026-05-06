# CHG-2209: Add Professional SOP Render Templates

**Applies to:** SHR project
**Last updated:** 2026-05-06
**Last reviewed:** 2026-05-06
**Status:** Proposed
**Date:** 2026-05-06
**Requested by:** Frank
**Priority:** Medium
**Change Type:** Normal

---

## What

Add professional SOP render templates so Screen Harness videos look like finished training/product material instead of prototype subtitles.

The first implementation should add a template architecture and ship one production-ready template:

- `debug`: current render behavior, kept backward-compatible.
- `training`: intro title card, countdown, and lower-corner step cards with sequence number, title, and instruction note.

Future templates should be designed for, but not implemented in the first PR:

- `compact`: small step cards, no intro, low visual interruption.
- `walkthrough`: training style with longer dwell, stronger highlights, and narration-friendly pacing.
- `presentation` / `ppt`: slide-like chapter cards and stronger section transitions for internal training decks.
- `product-demo`: polished product marketing/demo style with intro, chapter cards, and restrained overlay copy.

Template extensibility should be handled in two phases:

1. **Now:** built-in template registry plus a stable `Template` protocol inside the repo.
2. **Later:** external plugin/extension loading after the protocol survives at least `training`, `compact`, and `presentation` usage.

## Why

The current demo renders subtitles as generic full-width overlays, which makes the output feel like a technical spike. The user wants professional video behavior:

- A clear white-background intro explaining what will be demonstrated.
- A countdown before the actual screen recording starts.
- Step guidance placed in a lower-left or lower-right card, not across the whole screen.
- Step numbers plus concise English demo text, e.g. `01 Open Chrome`.
- Multiple future presentation modes for different SOP/video scenarios.

Trinity consultation with GLM, DeepSeek, and Claude Code agreed that this should be solved as a render-template layer, not merely with better generated copy.

## Impact Analysis

- **Systems affected:** Rendering pipeline, ASS generation, timeline helper API, CLI render options, metadata, demo script, tests, README, `SKILL.md`, `install.md`.
- **User-visible behavior:** Users can choose `render(template="training")` or `screen-harness render <id> --template training` to get a professional intro/countdown and step-card overlays.
- **Data affected:** `timeline.json` gains optional additive fields only: top-level `intro` metadata and optional `note` / `number` on `step` events. `metadata.json` records render template/provenance. `raw.mp4` remains immutable.
- **Compatibility:** Existing recordings render with `debug` behavior by default. Old timelines without `intro` or `note` remain valid.
- **Rollback plan:** Revert template modules, CLI/helper signature additions, intro rendering/concat code, and demo/doc/test changes. Existing `raw.mp4` and `timeline.json` files remain usable through the `debug` renderer.

## Implementation Plan

1. Add `src/screen_harness/templates/` with a minimal `Template` protocol, built-in registry, `debug`, and `training`.
2. Keep the current ASS behavior as `debug`; avoid broad refactors that risk breaking existing output.
3. Add optional timeline fields:
   - top-level `intro`: title/subtitle/countdown data.
   - `step.note`: short instruction body for step cards.
   - `step.number`: optional explicit sequence override; otherwise auto-number at render time.
4. Extend helpers:
   - `start_recording(name, intro=None, template=None, ...)` as light sugar.
   - `intro(title, subtitle=None, countdown=5)`.
   - `step(title, note=None, ...)`.
   - `render(template=None)`.
5. Extend CLI:
   - `screen-harness render <recording_id> --template training`
   - preserve `screen-harness render <recording_id>` as default/backward-compatible behavior.
   - keep manual flag parsing small for this PR; move to `argparse` only if another render flag is added.
6. Generate intro as a separate white-background pre-roll clip with red title/subtitle/countdown, then concat with the rendered main recording.
7. Render main recording in `training` mode with lower-corner step cards:
   - sequence number and title line.
   - note/instruction line.
   - light translucent card, restrained size, CJK-capable font preference.
   - larger title/note sizing and enough bottom margin to avoid clipped wrapped text.
8. Record render provenance in `metadata.json`, including selected template and render timestamp.
9. Update the Chrome/GitHub demo to use `training`.
10. Add focused tests for template dispatch, ASS generation, intro timing, CLI/helper wiring, metadata, and backward compatibility.


## Consultation Summary

Consulted:

- GLM through Trinity-compatible `droid` provider.
- DeepSeek through Trinity provider wrapper.
- Claude Code through local `claude` CLI because `claude-code` is not currently registered as a Trinity provider in `~/.codex/trinity.json`.

Consensus:

- Template modes are the right abstraction.
- First PR should not implement a full external plugin system.
- `raw.mp4` must remain immutable; templates are views over `timeline.json`.
- `intro` content belongs to the timeline; selected template belongs to render metadata.
- `step.note` should be first-class instead of inferring all notes from nearby `caption` events.
- `training` should be the first professional template; additional modes should follow only after the base protocol proves stable.


## Template / Extension Decision

Do not implement external plugin loading in the first PR.

Use this progression:

1. Built-in registry: `get_template("debug")`, `get_template("training")`.
2. Stable internal protocol after at least two real templates.
3. Later extension options:
   - Python entry points, e.g. `screen_harness.render_templates`.
   - Project-local template packages under `agent-workspace/render-templates/`.
   - Data-only theme overrides for colors/fonts/card position after behavior templates are stable.

Reason: templates may need code, not just configuration, because they generate ASS, intro specs, timing, and possibly FFmpeg composition plans. Freezing a plugin API before `training` and `presentation` exist would likely create churn.


## Visual Defaults For First Template

- Intro: white background, red title, dark gray subtitle, large centered countdown `5 4 3 2 1`.
- Main overlay: lower-corner by default, light translucent card with dark text.
- Step title: `01  Open Chrome`, bold, red/orange accent.
- Step note: smaller dark instruction line, wrapped conservatively.
- Highlight boxes: blue by default in professional demos, with per-event color override through `highlight_region(..., color=...)`.
- Dwell: no overlap with next step; clamp card duration to a professional range.
- Avoid full-screen subtitle blocks in `training`.


## Timeline Field Shape

The new fields are optional and additive. Example:

```json
{
  "intro": {
    "title": "This video demonstrates the Screen Harness GitHub repository",
    "subtitle": "Open Chrome, visit the project page, and inspect the file structure",
    "countdown": 5
  },
  "events": [
    {
      "id": "evt_002",
      "t": 0.0,
      "type": "step",
      "title": "Open Chrome",
      "note": "Launch the browser and prepare to visit the repository",
      "number": 1
    }
  ]
}
```

Rules:

- `intro.title`: optional string; default can derive from timeline title.
- `intro.subtitle`: optional string.
- `intro.countdown`: integer seconds; `0` disables countdown/pre-roll.
- `step.note`: optional string; if empty, render only number plus title.
- `step.number`: optional integer; if missing, auto-number only `step` events in timeline order. `chapter` events do not increment step numbers.


## Edge Cases To Cover

- Unknown template name fails clearly.
- `training` with no `intro` falls back to no intro pre-roll and still renders step cards.
- `intro.countdown = 0` skips intro generation.
- Empty `step.note` renders a title-only card.
- Long CJK titles do not crash and are escaped for ASS.
- Main recording resolution/fps drives generated intro canvas.


## Font Strategy

Training mode demo copy should be English-only. The renderer should still prefer CJK-capable fonts so non-demo recordings can render international text safely, in this order:

1. `PingFang SC`
2. `Hiragino Sans GB`
3. `Noto Sans CJK SC`
4. `Microsoft YaHei`
5. `Arial`

The first PR should not bundle fonts. It should encode this preference in ASS style defaults and document that visual QA is required on the target machine. If rendered CJK text shows missing glyphs, font bundling or `fontsdir` becomes a follow-up CHG.


## Testing / Verification

Use a four-layer test strategy:

1. **Unit tests:** template registry, ASS text generation, helper signatures, render command builders, and unknown template errors.
2. **BDD acceptance tests:** pytest scenarios written in Given/When/Then shape that exercise user-facing behavior without launching a browser. Example: given a timeline with intro and two steps, when rendered with `training`, then intro ASS and numbered step cards are produced and markdown remains stable.
3. **Hermetic E2E render tests:** generate a synthetic FFmpeg source video, create `timeline.json`, run the real `render(template="training")` pipeline, and assert `final.mp4` plus metadata exist. This can run in CI when FFmpeg supports ASS/subtitles and should skip clearly otherwise.
4. **Manual or scheduled UI E2E:** run `examples/expense_sop.py` to open Chrome and visit GitHub. Keep this out of required PR CI because it depends on macOS screen-recording permissions, Chrome availability, network, and desktop focus.

Required checks for this PR:

- Unit tests for template registry and unknown template errors.
- Unit tests for `training` ASS containing step number/title/note and lower-corner alignment.
- Unit tests for countdown ASS/timing.
- CLI tests for `render --template training`.
- Helper tests for `intro()`, `step(note=...)`, and `render(template=...)`.
- Backward-compatibility test for default `debug` render path.
- Render command tests for intro + main composition.
- BDD acceptance test for the professional training-video scenario.
- Hermetic FFmpeg E2E render test using generated test video when available in CI/local environment.
- `uv run --python 3.14 pytest -q`
- `uv run --python 3.14 python -m compileall -q src tests examples`
- `af validate`


## CI/CD Test Design

PR CI should stay aggressive but deterministic:

- Keep Python at `3.14`.
- Run unit, BDD, and hermetic E2E tests in the same `pytest` job.
- Let FFmpeg E2E skip only when the runner lacks required FFmpeg filters; do not skip ordinary Python tests.
- Do not run the real Chrome demo on every PR.

Later CI expansion:

- Add a scheduled macOS workflow for real Chrome recording once the demo stabilizes.
- Store rendered demo videos as artifacts for visual review.
- Add screenshot/frame sampling after templates become more visual and subjective.


## Out Of Scope For First PR

- Full external plugin loading.
- `compact`, `walkthrough`, `presentation`, or `product-demo` implementations.
- Theme JSON editor.
- Outro cards.
- Animated transitions.
- AI copywriting changes.
- Audio narration changes.
- Changes to recorder/transcription/redaction internals unless required by render metadata.

---

## Change History

| Date | Change | By |
|------|--------|----|
| 2026-05-06 | Initial version | — |
| 2026-05-06 | Filled render-template proposal from Trinity consultation | Codex |
| 2026-05-06 | Added CHG clarifications from GLM and DeepSeek fast-review | Codex |
