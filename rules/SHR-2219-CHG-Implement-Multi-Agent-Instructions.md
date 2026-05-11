# CHG-2219: Implement Multi-Agent Instructions Packaging (D3)

**Applies to:** SHR project
**Last updated:** 2026-05-12
**Last reviewed:** 2026-05-12
**Status:** Proposed
**Date:** 2026-05-12
**Requested by:** Frank Xu (D3 in SHR-2212)
**Priority:** Medium
**Change Type:** Normal
**Targets:** AGENTS.md (new), CLAUDE.md (new), .github/copilot-instructions.md (new), SKILL.md (rewrite), scripts/sync_agent_docs.py (new), scripts/check_agent_docs.py (new), scripts/agent-docs-tails/{claude,copilot,skill}.md (new), .github/workflows/ci.yml (new agent-docs job), README.md, tests/
**Implements:** SHR-2215 PRP R2.1 (Approved, Trinity 3/3 PASS @ 9.0)

---

## What

Implement PRP-2215 R2.1 verbatim. Deliverables:

1. **`AGENTS.md` at repo root** — single source of truth (LF Agentic AI
   Foundation spec, Feb 2026). Distilled from current `SKILL.md` body
   (install, helper API table, recording-script shape, AI SOP generation,
   redaction). Plain Markdown, no frontmatter. ≤ ~250 lines.

2. **`CLAUDE.md` at repo root** — thin stub. Banner:
   `<!-- GENERATED FROM AGENTS.md + scripts/agent-docs-tails/claude.md -->`
   plus SHA256 of the canonicalised source. Preamble: "Claude Code: read
   this first; full agent guidance lives in AGENTS.md. See also SKILL.md
   for the on-demand Skill bundle." Then the AGENTS.md body. Tail content
   (Claude-Code-specific notes) appended from `scripts/agent-docs-tails/claude.md`.

3. **`.github/copilot-instructions.md`** — same shape. Banner notes the
   per-user opt-in (`github.copilot.chat.codeGeneration.useInstructionFiles`)
   so users aren't misled into thinking it's auto-read everywhere.

4. **`SKILL.md` rewrite** as Anthropic Skill bundle entry point:
   - Frontmatter: `name`, `description` (≤ 1024 chars; CI-enforced).
   - Body: thin pointer to AGENTS.md + "When to invoke this skill" stanza
     (the Skill-specific content from `scripts/agent-docs-tails/skill.md`).

5. **DROP `agent.md`** (lowercase) — no consumer. Already not in repo (no
   delete needed); just document the decision.

6. **`scripts/sync_agent_docs.py`**:
   - Read `AGENTS.md` (source of truth) + the small per-target tail files
     in `scripts/agent-docs-tails/{claude,copilot,skill}.md`.
   - For each target file, emit `banner + body + tail` with the
     canonicalised-source SHA256 in the banner.
   - **Canonicalisation rules**: LF line endings only, single trailing
     newline, YAML keys (SKILL.md frontmatter) sorted alphabetically. Hash
     inputs only the canonicalised form so editor whitespace doesn't cause
     spurious CI failures.
   - SKILL.md `description` length asserted ≤ 1024 chars before emit (raise
     if violated).
   - Idempotent: running twice produces identical output.

7. **`scripts/check_agent_docs.py`**: runs the sync into a tempdir, diffs
   against the checked-in files, exits 1 with a clear "Run
   scripts/sync_agent_docs.py and commit" message on any drift.

8. **CI `agent-docs` job** in `.github/workflows/ci.yml`: runs
   `check_agent_docs.py`. Independent of `test` / `alfred` / `package` jobs.

9. **README update**: rewrite "Use as a Claude Skill" section to:
   - List which file each tool reads (with the Copilot opt-in caveat).
   - Point to `AGENTS.md` as canonical source.
   - Mention the sync command for editors.
   - Pin consumer minimum versions (PRP-2215 R2.1 §Risks): Codex CLI ≥ Feb
     2026 release, Cursor/Windsurf/Amp ≥ 2026.02.

10. **Optional `GEMINI.md`** — leave out for now. PRP R2.1 marks as
    opt-in `pyproject.toml [tool.screen-harness] gemini = true`; defer
    until first Gemini user asks. CHG-only mention.

## Why

D3 in SHR-2212. Currently only `SKILL.md` exists with Anthropic-style
frontmatter, mis-aligned with the AGENTS.md ecosystem standard that
emerged in 2026. Users of Codex/Copilot/Cursor/Claude Code/Gemini have to
copy-paste guidance into per-tool config. Adopting AGENTS.md as canonical
source eliminates drift and keeps the various tool-specific files in sync
via a tested, hashed pipeline.

## Impact

- New files at root: `AGENTS.md`, `CLAUDE.md`. New file at
  `.github/copilot-instructions.md`.
- `SKILL.md` rewritten (body shrinks ~80%; frontmatter tightened).
- New scripts under `scripts/` (small Python; no runtime deps beyond
  stdlib).
- New CI job `agent-docs`.
- No code changes in `src/`. No test changes outside the new
  `tests/test_agent_docs_sync.py`.
- Behaviour change: editing `SKILL.md` directly is now disallowed (CI
  fails); edits go through `AGENTS.md` + sync. The banner makes this
  explicit in every generated file.

## Plan

Follow COR-1500 TDD overlay: RED → GREEN → REFACTOR.

1. **RED**: pure-Python unit tests in `tests/test_agent_docs_sync.py`:
   - `test_parse_skill_frontmatter_roundtrip` — round-trip a fixture
     SKILL.md → `(frontmatter_dict, body)` → recombine → byte-equal.
   - `test_canonicalise_idempotent` — `canonicalise(canonicalise(x)) == canonicalise(x)`.
   - `test_canonicalise_normalises_line_endings` — CRLF input → LF output.
   - `test_render_target_claude_includes_agents_body` — golden fixture for
     `render_target("claude", source, tail)`.
   - `test_render_target_copilot_carries_opt_in_caveat`.
   - `test_render_target_skill_strips_frontmatter_into_yaml` — SKILL.md
     output has YAML frontmatter, sorted keys.
   - `test_skill_description_too_long_raises` — `description` > 1024 chars
     in source AGENTS.md frontmatter (or tail) raises.
   - `test_sync_is_idempotent` — run sync twice; second run produces no
     diff.
2. **GREEN — pure-Python core**: implement `sync_agent_docs.py` parse,
   canonicalise, render functions to pass the unit tests.
3. **RED**: `tests/test_agent_docs_drift_detection.py`:
   - `test_check_returns_zero_on_clean_repo` — run sync, then check; exit 0.
   - `test_check_returns_nonzero_after_manual_edit` — touch a generated
     file with a stray byte; check exits 1 with clear message.
4. **GREEN — drift detection**: implement `check_agent_docs.py`.
5. **Author content**:
   - Write `AGENTS.md` (distill current `SKILL.md` body + README install).
   - Write `scripts/agent-docs-tails/claude.md` (Claude-Code-specific
     notes: skills, slash commands, alfred hooks).
   - Write `scripts/agent-docs-tails/copilot.md` (Copilot Chat instruction
     opt-in note, instructions file applyTo).
   - Write `scripts/agent-docs-tails/skill.md` (Anthropic Skill "when to
     invoke" stanza).
   - Run `scripts/sync_agent_docs.py` to emit CLAUDE.md, copilot-instructions.md,
     SKILL.md.
6. **CI**: add the `agent-docs` job to `.github/workflows/ci.yml`. Runs on
   ubuntu-latest, uses `uv run python scripts/check_agent_docs.py`.
7. **README rewrite**: update "Use as a Claude Skill" section.
8. **REFACTOR**: tighten error messages, ensure scripts are runnable from
   any cwd (compute paths relative to repo root, not cwd).
9. Run full local gate: `uv run pytest -q`, `uv run python -m compileall`,
   `uvx --from fx-alfred af validate`, plus `python scripts/check_agent_docs.py`
   manually to confirm zero drift.

## Rollback

Revert this branch's commits on `main`. New files are additive (AGENTS.md,
CLAUDE.md, copilot-instructions.md, scripts/). SKILL.md was rewritten —
the original is in PR history. The CI `agent-docs` job is additive — its
removal doesn't break other jobs.

## Tests Gate (CI must pass)

- All existing tests still pass (252 → 252+ baseline).
- New unit tests for parse / canonicalise / render / drift detection.
- New `agent-docs` CI job exits 0 on a clean repo.
- Compileall clean.
- `af validate` 0 issues.
- `python scripts/check_agent_docs.py` exits 0 on a clean repo.

## Approval

- [ ] Approved by: <reviewer> on <date>

---

## Change History

| Date | Change | By |
|------|--------|----|
| 2026-05-12 | Initial CHG, implements approved PRP-2215 R2.1 | Claude Code |
