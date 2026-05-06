# PLN-2210: Professional Render Template Milestones

**Applies to:** SHR project
**Last updated:** 2026-05-06
**Last reviewed:** 2026-05-06
**Status:** Draft
**Related:** SHR-2209, SHR-2201

---

## What Is It?

Milestone plan for evolving Screen Harness from prototype subtitles to professional render templates. This plan breaks the work into reviewable PRs and estimates the cost of each stage in approximate production Python LOC, test LOC, docs, and risk.

Baseline at planning time:

- Production Python: about `1.3k` nonblank/non-comment LOC under `src/screen_harness/`.
- Tests: `36` tests after the CI PR.
- Current render behavior: one ASS style for subtitles/step titles plus drawbox overlays.
- Constraint: `raw.mp4` remains immutable and `timeline.json` remains the editable source of truth.

---

## Goals

- Improve output quality from technical subtitle proof to professional SOP/training video.
- Add template modes incrementally, with each mode justified by a real video scenario.
- Keep render templates as presentation views over the same timeline, not as new recording formats.
- Avoid an external plugin API until the internal template protocol survives multiple built-in modes.
- Keep each milestone small enough for one PR and one review cycle.
- Track expected code cost before implementation so the project does not drift into a large renderer rewrite.


## LOC Estimate Method

LOC estimates are planning ranges, not hard caps.

- **Prod Python LOC:** nonblank/non-comment lines added or materially changed under `src/screen_harness/`.
- **Test LOC:** nonblank/non-comment lines under `tests/`.
- **Docs LOC:** README / rules / example documentation.
- Generated files, `recordings/`, and build artifacts are excluded.

The estimates assume conservative implementation using the existing FFmpeg/ASS pipeline. If we introduce Playwright screenshots, image generation, GUI, or real plugin sandboxing, the cost changes materially.

## Milestones

| # | Milestone | Scenario | User-visible feature | Estimated Cost | Status |
|---|-----------|----------|----------------------|----------------|--------|
| 1 | Training Template MVP | SOP/tutorial video | White intro, countdown, lower-corner numbered step cards | +350-550 prod Python LOC, +250-400 test LOC, +50-100 docs LOC | Planned |
| 2 | Compact Template | Fast internal walkthrough | No intro, small low-interruption step card, same timeline fields | +120-220 prod Python LOC, +120-220 test LOC, +30-60 docs LOC | Proposed |
| 3 | Walkthrough Template | Narrated process walkthrough | Longer dwell, stronger highlight pacing, narration-friendly step cards | +180-320 prod Python LOC, +160-280 test LOC, +40-80 docs LOC | Proposed |
| 4 | Presentation/PPT Template | Training/deck-like SOP | Slide-like chapter cards, stronger section transitions, optional outro | +250-450 prod Python LOC, +200-350 test LOC, +50-100 docs LOC | Proposed |
| 5 | Product Demo Template | Product/showcase video | Polished intro, restrained feature callouts, brand/demo pacing | +250-450 prod Python LOC, +200-350 test LOC, +50-120 docs LOC | Proposed |
| 6 | Template Extension API | Team/project customization | External entry points or project-local templates after protocol stabilizes | +350-700 prod Python LOC, +300-500 test LOC, +100-180 docs LOC | Deferred |


## Milestone 1: Training Template MVP

**Goal:** First visible quality jump. Make the Safari/GitHub demo feel like a real SOP/training video without building a general theme/plugin system.

**Features:**

- Built-in template registry: `debug`, `training`.
- `debug` preserves current behavior.
- `training` adds:
  - white intro card;
  - red title/subtitle;
  - countdown `5 4 3 2 1`;
  - lower-right or lower-left step card;
  - sequence number, step title, and step note.
  - light card default with larger text and enough bottom margin for wrapped notes.
  - blue highlight-box default plus per-event highlight color override.
- Additive timeline fields:
  - top-level `intro`;
  - `step.note`;
  - optional `step.number`.
- Helper API:
  - `intro(title, subtitle=None, countdown=5)`;
  - `step(title, note=None, ...)`;
  - `render(template="training")`.
- CLI:
  - `screen-harness render <id> --template training`.
- Render metadata:
  - selected template;
  - render timestamp;
  - FFmpeg path/version if available.
- Update Safari/GitHub demo to use `training`.

**Cost / Risk:**

- Estimated +350-550 production Python LOC.
- Main complexity: intro clip generation + concat with the main render.
- Main visual risk: CJK font fallback and ASS card appearance across FFmpeg builds.
- Main compatibility risk: default render must stay backward-compatible.

**Exit Criteria:**

- Existing tests pass under Python 3.14.
- New template tests cover registry, step-card ASS, intro timing, CLI/helper wiring, metadata, BDD acceptance behavior, hermetic E2E rendering, and default backward compatibility.
- Real demo renders `final.mp4` with intro/countdown and lower-corner step cards as a manual acceptance check.
- `debug` mode still works for old recordings.
- Review confirms no full-screen subtitle blocks in `training`.

**Test Design:**

- Unit: small Python tests for registry, timeline fields, command construction, helpers, and CLI flag parsing.
- BDD: pytest acceptance scenario using Given/When/Then structure, no browser, no OS permissions, no network.
- E2E: synthetic FFmpeg `raw.mp4` plus real `render(template="training")`; skip only if FFmpeg lacks ASS/subtitles support.
- Manual UI E2E: `examples/expense_sop.py` opens Safari and visits GitHub; keep it outside required PR CI until a scheduled macOS visual-review workflow exists.

**Extra Test Cost:**

- BDD acceptance scenario: about +35-60 test LOC.
- Hermetic FFmpeg E2E: about +60-100 test LOC.
- Manual UI E2E docs/checklist: about +15-30 docs LOC.


## Milestone 2: Compact Template

**Goal:** Add a practical low-noise mode for internal recordings where intro/countdown is too much.

**Features:**

- Built-in `compact` template.
- No intro by default.
- Smaller step card, shorter dwell, less visual weight.
- Same `step.note` and numbering fields as `training`.
- CLI/helper support reuses existing template flag.

**Cost / Risk:**

- Estimated +120-220 production Python LOC because the template infrastructure already exists.
- Main risk: template duplication if `training` and `compact` do not share card layout helpers.
- Useful as the first validation that the internal template protocol is not overfit to `training`.

**Exit Criteria:**

- Same timeline can render under `debug`, `training`, and `compact`.
- Compact cards do not obscure common browser UI areas.
- Tests prove no intro clip is generated for `compact`.


## Milestone 3: Walkthrough Template

**Goal:** Support narrated process walkthroughs where viewers need more time to follow actions and highlights.

**Features:**

- Built-in `walkthrough` template.
- Longer step-card dwell than `training`.
- Stronger highlight-region timing.
- Optional narration-friendly captions under the step card when `caption` events exist.
- Same intro model as `training`, but intro can be disabled for shorter recordings.

**Cost / Risk:**

- Estimated +180-320 production Python LOC.
- Main risk: becoming too visually busy if captions, highlights, and step cards all compete.
- Useful for validating that template behavior can vary in timing/pacing, not only colors/layout.

**Exit Criteria:**

- Same timeline can render differently under `training` and `walkthrough`.
- Walkthrough timing does not overlap step cards or obscure important UI.
- Tests cover longer dwell and highlight/caption coexistence.


## Milestone 4: Presentation / PPT Template

**Goal:** Support deck-like training videos and internal enablement where chapter transitions matter more than live screen fidelity.

**Features:**

- Built-in `presentation` or `ppt` template.
- Chapter title cards from `chapter()` events.
- Stronger section transitions between groups of steps.
- Optional outro/end card.
- Step cards may move to slide-like lower-third layout.

**Cost / Risk:**

- Estimated +250-450 production Python LOC.
- Main complexity: mapping `chapter` events to generated interstitial cards without shifting raw timeline semantics.
- Main product risk: this mode could turn into a full slide engine; keep it template-level, not a deck builder.

**Exit Criteria:**

- Chapter events create visible section cards.
- Raw screen timing remains unchanged after each transition.
- Markdown SOP generation still uses the same timeline semantics.


## Milestone 5: Product Demo Template

**Goal:** Make a polished product-showcase mode for external demos, founder videos, and release walkthroughs.

**Features:**

- Built-in `product-demo` template.
- More polished intro and restrained overlay copy.
- Feature callout cards.
- Optional brand/title metadata.
- More careful default placement so overlays do not cover GitHub/browser navigation.

**Cost / Risk:**

- Estimated +250-450 production Python LOC.
- Main risk: visual preferences become subjective; require screenshot/video review before merging.
- May need the first data-only theme override for colors and branding.

**Exit Criteria:**

- Product demo can render the Safari/GitHub example without looking like an internal training video.
- Default visual language remains restrained and readable.
- No external plugin loading yet unless Milestone 5 is approved.


## Milestone 6: Template Extension API

**Goal:** Let teams load project-specific templates without changing Screen Harness core.

**Features:**

- Stable `Template` protocol.
- External loading options:
  - Python entry point group, e.g. `screen_harness.render_templates`;
  - project-local templates under `agent-workspace/render-templates/`;
  - data-only theme overrides for simple colors/fonts/card placement.
- Template discovery command:
  - `screen-harness templates list`;
  - `screen-harness templates inspect <name>`.
- Validation for unsupported templates and missing dependencies.

**Cost / Risk:**

- Estimated +350-700 production Python LOC.
- Main risk: plugin safety and API stability.
- Do not start until at least two built-in templates prove the protocol shape.

**Exit Criteria:**

- A project-local template can be loaded in a controlled test fixture.
- Bad templates fail with clear errors.
- Built-in templates remain first-class and unaffected.


## Recommended Immediate PR

Implement only Milestone 1.

PR title:

```text
feat(render): add training template with intro and step cards
```

Scope:

- Built-in registry + `debug`/`training`.
- Optional `intro` + `step.note`.
- `render(..., template="training")`.
- CLI `--template`.
- Safari/GitHub demo updated.
- Tests and one real render smoke if local FFmpeg supports it.

Do not implement `compact`, `presentation`, `product-demo`, or plugin loading in this PR.


## Decision Gates

- After Milestone 1: decide whether visual quality is good enough to continue templates or first polish `training`.
- After Milestone 2: decide whether the internal protocol is stable enough for more modes.
- Before Milestone 6: require evidence from at least three built-in templates and at least one real team customization request.

---

## Change History

| Date | Change | By |
|------|--------|----|
| 2026-05-06 | Initial version | — |
| 2026-05-06 | Filled milestone plan with feature and LOC cost estimates | Codex |
| 2026-05-06 | Added walkthrough milestone and review clarifications from Trinity fast-review | Codex |
