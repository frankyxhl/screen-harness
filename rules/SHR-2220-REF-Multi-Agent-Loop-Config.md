# REF-2220: Multi-Agent Loop Project Configuration

**Applies to:** SHR project (screen-harness)
**Last updated:** 2026-05-15
**Last reviewed:** 2026-05-15
**Status:** Active
**Instantiates:** COR-1622 (parameter schema)
**Adopts:** COR-1617 (Multi-Agent Workflow Loop)
**Closes:** GitHub issue #4

---

## What Is It?

PRJ-layer instantiation of COR-1622 for the screen-harness repo. Fills in concrete values for every required key in the COR-1622 parameter schema so the COR-1617 loop can run against this repo.

## Why

screen-harness is a solo-owner CLI tool with a growing CHG cadence (D1 / D2 / D3 shipped in May 2026). Issue intake is currently ad-hoc — there is no consent gate, no review panel, and no worker-dispatch rule. Adopting COR-1617 gives the project a structured intake → plan-review → implement → code-review → merge pipeline that matches the workflow already used in trinity / alfred.

---

## Configuration

### Identity & repository

| Key | Value |
|-----|-------|
| `<repo>` | `frankyxhl/screen-harness` |
| `<repo-owner>` | `frankyxhl` |
| `<repo-trusted-reactor-list>` | `[frankyxhl]` |
| `<gh-write-identity>` | `ryosaeba1985` |
| `<pr-push-remote>` | `origin` |

Notes:
- Single-remote project (no fork topology) — feature branches push to `origin`; PRs target `origin/main`. The "never push to `origin/main` directly" invariant still holds.
- `<gh-write-identity>` follows the global user rule (see `~/.claude/CLAUDE.md` §User-Level GitHub Identity Rule). Verify with `gh auth status` per COR-1505 before any public mutation.

### Consent gate (COR-1618)

| Key | Value |
|-----|-------|
| `<consent-signal>` | `rocket` |
| `<intake-quality-mode>` | `2FA` |
| `<intake-quality-label>` | `blueprint-ready` |
| `<intake-quality-applier-set>` | `[ryosaeba1985]` |

Notes:
- 2FA: an issue is auto-pick-eligible only when (a) a member of `<repo-trusted-reactor-list>` has reacted with `rocket` on the **issue body** AND (b) the most-recent `LABELED` event for `blueprint-ready` was applied by a member of `<intake-quality-applier-set>`.
- The label must exist on the repo before the loop can run. Create once with:
  ```bash
  gh label create blueprint-ready \
    --description "Intake spec reviewed and ready for the multi-agent loop" \
    --color BFD4F2
  ```
- Solo-owner setup: `ryosaeba1985` is the only authorized applier. This means Claude's own `gh` writes (which use `ryosaeba1985`) can both apply the label and pass the 2FA check, provided the rocket reaction came from `frankyxhl` first.

### Review panel (COR-1602 binding)

| Key | Value |
|-----|-------|
| `<panel-providers>` | `[glm, deepseek]` |
| `<weights-doc>` | `{CHG: COR-1609, ADR: COR-1609, RFC: COR-1608, inline-PR-body: COR-1609}` |
| `<spec-format>` | `CHG` |
| `<panel-pass-threshold>` | `9.0` |

**Deviation from COR-1622 — panel size = 2:**

COR-1622 §Review panel states "Minimum **3 viable** verdicts required to enforce the gate." This config intentionally uses only 2 providers (`glm`, `deepseek`).

Consequences (documented explicitly so future runs do not silently re-derive them):

1. **The COR-1617 §Phase 4 PASS gate cannot be enforced** in its all-individual-≥9.0 form. With only 2 reviewers, "all-individual" still applies arithmetically, but the schema's redundancy invariant is not met.
2. Panel verdicts are treated as **advisory** rather than gating. Plan-review still runs and findings are still surfaced; merge decisions remain manual until the panel is expanded to ≥3.
3. **Reviewer B in COR-1617 §Phase 8 triage** must be the operator (Frank), not a third panel provider — the panel cannot self-supply an independent third opinion.
4. If either provider's CLI is unavailable in a session, the panel collapses to single-reviewer; surface and pause rather than proceeding.

To restore gate enforcement, add a third provider (recommended: `codex`) and remove this deviation block.

### Worker dispatch (COR-1619)

| Key | Value |
|-----|-------|
| `<worker-agent>` | `trinity-glm via droid exec` |
| `<worker-min-loc>` | `30` (default) |

### R-count cap (COR-1617 §Phase 8)

| Key | Value |
|-----|-------|
| `<max-r-count>` | `10` (default) |
| `<max-r-count-extension>` | `3` (default) |
| `<convergence-severity>` | `advisory` (default) |

### Resilience

| Key | Value |
|-----|-------|
| `<cli-retry-attempts>` | `3` (default) |
| `<cli-retry-backoff-seconds>` | `600` (default) |
| `<cli-retry-on-failure>` | `pause-and-ask` (default) |

Interaction with the 2-provider deviation: `mark-non-viable` is unsafe here — marking one provider non-viable leaves a single-reviewer panel, which is below even this config's already-degraded floor. `pause-and-ask` is the only sound default while `<panel-providers>` has 2 entries.

### Bot polling (COR-1615 binding)

| Key | Value |
|-----|-------|
| `<bot-actors>` | `[chatgpt-codex-connector[bot]]` |

Note: only `chatgpt-codex-connector[bot]` is installed against this repo today. If additional review bots are installed later (e.g. Sourcery, CodeRabbit), add their App logins here.

### Loop primitives (COR-1620)

| Key | Value |
|-----|-------|
| `<wakeup-tool>` | `ScheduleWakeup` |
| `<idle-cap>` | `12` (default) |
| `<merge-watch-cap>` | `24` (default) |

---

## Guard Rails

- This is a PRJ-layer doc. Changes to the COR-1622 schema itself go through the alfred/trinity upstream, not here.
- Substituting another project's weights doc (e.g. `TRN-1800`) is a guard-rail violation per COR-1622. screen-harness uses the alfred-style map → COR-1608/1609/1610.
- The 2-provider panel is an **intentional deviation**, not a default. Removing the deviation block in §Review panel requires growing `<panel-providers>` to ≥3 first; deleting the block without expanding the panel re-introduces the schema violation silently.

---

## Change History

| Date | Change | By |
|------|--------|----|
| 2026-05-15 | Initial PRJ instantiation of COR-1622 — closes issue #4. Panel intentionally sized at 2 (advisory mode); 2FA consent with `blueprint-ready` label | Claude Code |
