# CHG-2219: Implement Multi-Agent Instructions Packaging (D3)

**Applies to:** SHR project
**Last updated:** 2026-05-12
**Last reviewed:** 2026-05-12
**Status:** Proposed
**Revision:** R2 — addresses Trinity R1 (GLM PASS 9.15, DeepSeek FAIL 7.7, MiniMax FAIL 8.4)
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
   Foundation spec, Feb 2026). Plain Markdown, no frontmatter. ≤ ~250 lines.
   Required H1/H2 outline (DeepSeek R1 A2):

   ```
   # Screen Harness — Agent Instructions
   ## When to use this project
   ## Install
   ## Recording script shape
   ## Helper API
   ## AI SOP generation
   ## Sensitive-info redaction
   ## Version compatibility (consumer minimums)
   ```

   Content distilled from current `SKILL.md` body + `README.md` install
   section. The "Version compatibility" section lists: Codex CLI ≥ Feb 2026
   release, GitHub Copilot Chat (with `useInstructionFiles` setting on),
   Cursor ≥ 2026.02, Windsurf ≥ 2026.02, Amp ≥ 2026.02, Devin (current).

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
   - Body: thin pointer to AGENTS.md + "When to invoke this skill" stanza.

   **Source of the YAML frontmatter** (DeepSeek R1 B2 / MiniMax R1 A3):
   the `name` and `description` (and only those two keys — any others
   raise during emit) live as **YAML frontmatter inside
   `scripts/agent-docs-tails/skill.md`**. **That tail file is hand-authored
   and never generated** (MiniMax R2 A1) — it is the canonical source for
   the two keys. The render function lifts that frontmatter, validates
   it (length + key whitelist), and re-emits it sorted at the top of
   `SKILL.md`. The body of `scripts/agent-docs-tails/skill.md` below its
   `---` separator becomes the Skill-specific stanza appended after the
   AGENTS.md pointer.

5. **DROP `agent.md`** (lowercase) — no consumer. Already not in repo (no
   delete needed); just document the decision.

6. **`scripts/sync_agent_docs.py`** (stdlib-only — no PyYAML):
   - Read `AGENTS.md` (source of truth) + the small per-target tail files
     in `scripts/agent-docs-tails/{claude,copilot,skill}.md`.
   - For each target file, emit `banner + body + tail` with the
     canonicalised-source SHA256 in the banner.
   - **Canonicalisation rules**: LF line endings only, single trailing
     newline, YAML keys (SKILL.md frontmatter) emitted via a hand-rolled
     2-key emitter (only `name` + `description` allowed; alphabetical
     order). Hash inputs only the canonicalised form so editor
     whitespace doesn't cause spurious CI failures. **No PyYAML
     dependency** — the schema is fixed at 2 keys, so a 10-line emitter
     gives byte-stable output without the PyYAML version-sensitivity
     (DeepSeek R1 B1, MiniMax R1 B3).
   - YAML emitter contract (pinned bytes):
     ```
     ---
     description: <single-line text, < 1024 chars, no embedded \n>
     name: <kebab-case identifier>
     ---
     ```
     `description` is single-line in the output — if the source text
     contains newlines, the emitter raises (the schema doesn't support
     multi-line descriptions; reformat the source).
   - **Emitter algorithm** (MiniMax R2 B4, pinned to avoid
     insertion-order accidents — Python 3.7+ dicts preserve insertion
     order, NOT alphabetical):
     ```python
     def emit_frontmatter(d: dict) -> str:
         allowed = {"name", "description"}
         extras = set(d) - allowed
         if extras:
             raise ValueError(f"Unknown frontmatter keys: {sorted(extras)}")
         lines = ["---"]
         for key in sorted(d.keys()):              # ← explicit alphabetical sort
             value = d[key]
             if "\n" in str(value):
                 raise ValueError(f"{key}: multi-line value not supported")
             if key == "description" and len(value) > 1024:
                 raise ValueError(f"description exceeds 1024 chars: {len(value)}")
             lines.append(f"{key}: {value}")
         lines.append("---")
         return "\n".join(lines) + "\n"
     ```
   - SKILL.md `description` length asserted ≤ 1024 chars before emit
     (raise if violated).
   - **Banner byte template** (MiniMax R1 A2, pinned verbatim):
     ```
     <!-- GENERATED FROM AGENTS.md + scripts/agent-docs-tails/<target>.md
          Source SHA256: <64-hex-chars>
          Edit AGENTS.md (or the tail file) and run scripts/sync_agent_docs.py. -->
     ```
     SHA256 field is exactly 64 hex chars, no spaces around. Trailing
     newline after the closing `-->`. Drift detection compares
     byte-for-byte after canonicalisation.
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
    until first Gemini user asks. **Add a one-line `# TODO(gemini):
    read pyproject [tool.screen-harness].gemini and emit GEMINI.md`
    in `sync_agent_docs.py` near the target dispatch** (GLM R1 A1)
    so the integration point is discoverable for D3.1.

## Why

D3 in SHR-2212.

### Note on scope atomicity (MiniMax R1 B1)

This CHG touches 9 surfaces across 4 classes — superficially a CLD-1802
cross-class violation that would normally split. **It does not split**
because the deliverables form a single sync pipeline whose pieces are
co-dependent: the script can't be tested without source + tails + fixtures,
the generated stubs can't exist without the script, and CI can't pass
without all of them landing together. Splitting would require a
scaffolding-only PR with no functional output. PRP-2215 R2.1 (Approved,
Trinity 3/3 PASS) explicitly bundles these as one delivery; this CHG
implements that bundle atomically. The Plan §1–§7 sequence keeps the
internal TDD discipline (RED-tested pure functions before AppKit-style
integration of generated files).
 Currently only `SKILL.md` exists with Anthropic-style
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

1. **RED**: pure-Python unit tests in `tests/test_agent_docs_sync.py`.

   **Test fixture paths** (MiniMax R1 B2, pinned):

   ```
   tests/fixtures/agent_docs/
     source_agents.md           # canonical AGENTS.md source for tests
     tail_claude.md             # claude tail (no frontmatter)
     tail_copilot.md            # copilot tail (no frontmatter)
     tail_skill.md              # skill tail WITH YAML frontmatter (name, description)
     expected_claude.md         # byte-exact expected output
     expected_copilot.md        # byte-exact expected output
     expected_skill.md          # byte-exact expected output (with emitted YAML frontmatter)
   ```

   Unit tests:
   - `test_parse_tail_frontmatter_roundtrip` — parse `tail_skill.md` →
     `(frontmatter_dict, body)` → recombine → byte-equal.
   - `test_canonicalise_idempotent` — `canonicalise(canonicalise(x)) == canonicalise(x)`.
   - `test_canonicalise_normalises_line_endings` — CRLF input → LF output.
   - `test_render_target_claude_matches_expected_fixture`.
   - `test_render_target_copilot_matches_expected_fixture` (verifies
     opt-in caveat present in output).
   - `test_render_target_skill_emits_sorted_yaml_frontmatter`
     (renamed from confusing "strips_frontmatter_into_yaml" — MiniMax R1 A8).
   - `test_skill_description_too_long_raises` — `description` > 1024 chars
     in `scripts/agent-docs-tails/skill.md` frontmatter raises.
   - `test_skill_frontmatter_rejects_unknown_keys` — only `name` +
     `description` allowed; anything else raises.
   - `test_yaml_emission_is_byte_stable_across_runs` (MiniMax R1 B3) —
     emit the same input 10 times; assert byte-identical output.
   - `test_sync_is_idempotent` — run sync twice; second run produces no
     diff.
2. **GREEN — pure-Python core**: implement `sync_agent_docs.py` parse,
   canonicalise, render functions to pass the unit tests.
3. **RED**: `tests/test_agent_docs_drift_detection.py`:
   - `test_check_returns_zero_on_clean_repo` — run sync, then check; exit 0.
   - `test_check_returns_nonzero_after_manual_edit_to_generated_file` —
     touch a generated file with a stray byte; check exits 1 with clear
     message.
   - `test_check_returns_nonzero_after_source_edit_without_resync`
     (GLM R1 A2) — touch `AGENTS.md` after a clean sync; check exits 1.
     Covers the real-world failure mode (forgetting to re-run sync).
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

`git revert <merge-commit-sha>` on `main`. New files are additive
(AGENTS.md, CLAUDE.md, copilot-instructions.md, scripts/). SKILL.md was
rewritten — to recover the pre-merge version explicitly:

```bash
git show <pre-merge-sha>:SKILL.md > SKILL.md
```

The CI `agent-docs` job is additive — its removal doesn't break other
jobs.

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
| 2026-05-12 | R2 — Address Trinity R1 (GLM PASS 9.15, DeepSeek FAIL 7.7, MiniMax FAIL 8.4): hand-rolled 2-key YAML emitter (no PyYAML dep) addressing DeepSeek B1 + MiniMax B3; declare SKILL.md frontmatter source = scripts/agent-docs-tails/skill.md (DeepSeek B2 + MiniMax A3); pin 7 fixture file paths (MiniMax B2); banner byte template + AGENTS.md heading outline pinned; atomicity justification + rollback commands; GEMINI.md TODO marker for D3.1 integration point; source-edit drift test (GLM A2). | Claude Code |
| 2026-05-12 | R3 — Address MiniMax R2 (FAIL 7.3): pin emitter algorithm with explicit `sorted(d.keys())` step (B4); declare `scripts/agent-docs-tails/skill.md` hand-authored (A1). GLM R2 PASS 9.35, DeepSeek R2 PASS 9.6 (both confirmed no regression). | Claude Code |
