# PRP-2215: Multi-Agent Instructions Packaging (AGENTS.md as source)

**Applies to:** SHR project
**Last updated:** 2026-05-11
**Last reviewed:** 2026-05-11
**Status:** Implemented
**Revision:** R2.1 — re-architected after R1 + web research; consumer-version pin from DeepSeek advisory
**Approved by:** Trinity R2 — glm PASS 9.00, deepseek PASS 9.0, minimax PASS 9.3 (3/3 unanimous)
**Related:** D3 in SHR-2212

---

## What Is It?

Adopt the 2026-standard **AGENTS.md** spec (Linux Foundation Agentic AI
Foundation) as the single source of truth for always-on coding-agent
instructions, and emit thin stubs for tool-specific files that do not yet
read AGENTS.md natively. Keep the existing `SKILL.md` as an *orthogonal*
artifact: it is the on-demand **Anthropic Claude Skill bundle** for the
Skills marketplace, not always-on instructions.

R1 reviewers (deepseek, glm, minimax all FAIL) plus web research established:

- AGENTS.md is read natively by **Codex CLI, GitHub Copilot, Cursor,
  Windsurf, Amp, Devin** (LF Agentic AI Foundation, Feb 2026).
- **Claude Code** reads **CLAUDE.md** (AGENTS.md support pending).
- **Gemini CLI** reads **GEMINI.md**.
- Anthropic Skills (`SKILL.md`) is a separate concept — a bundle (folder
  with `SKILL.md` + `scripts/`) that Claude invokes on demand, with
  required frontmatter limited to `name` + `description`.
- Copilot reads `.github/copilot-instructions.md` *only* in Copilot Chat
  (VS Code / GitHub.com) when the user has
  `github.copilot.chat.codeGeneration.useInstructionFiles` enabled.

Original R1 plan ("SKILL.md is source") had the layering wrong; R2 fixes it.

---

## Problem

Today only `SKILL.md` exists. Users of Codex/Copilot/Cursor/Claude Code/
Gemini have to copy-paste guidance into per-tool config. There is no
contract that keeps the surfaces in sync.

---

## Scope

**In scope:**

- **Create `AGENTS.md` at repo root** as the canonical, always-on
  instructions document. Content: distilled from current `SKILL.md` body —
  install, helper API table, recording-script shape, AI SOP generation,
  redaction. No frontmatter (the spec is plain Markdown). ≤ ~250 lines.

- **Create `CLAUDE.md` at repo root** with:
  - One-line preamble: "Claude Code: read this first; full agent guidance
    lives in AGENTS.md. See also SKILL.md for the Skill bundle."
  - Claude-Code-specific notes (e.g., suggested tools, slash commands the
    repo defines).
  - `<!-- GENERATED FROM AGENTS.md + .claude-md.tail.md -->` banner.

- **Create `.github/copilot-instructions.md`** with:
  - Banner: "Generated from AGENTS.md. Copilot Chat reads this when the
    `github.copilot.chat.codeGeneration.useInstructionFiles` setting is
    enabled (per-user, opt-in)."
  - Body: identical to AGENTS.md.

- **Keep `SKILL.md`** as the Anthropic Skill bundle entry point:
  - Tighten frontmatter to the documented Anthropic schema: `name`,
    `description` (≤ 1024 chars, asserted in CI).
  - Body becomes a *thin pointer* to AGENTS.md plus a "When to invoke this
    skill" stanza (the only Skill-specific content). Skill bundles are
    optimised for short skim-load by Claude; AGENTS.md is the deep
    reference.

- **Drop `agent.md`** — no consumer (R1 minimax flagged this; web research
  confirms there is no widely-deployed lowercase-`agent.md` reader).

- **Optional `GEMINI.md`** stub (same pattern as `.github/copilot-instructions.md`).
  Marked optional in the script — emit only if `pyproject.toml`
  `tool.screen-harness.gemini = true`. Default off until a user asks.

- **`scripts/sync_agent_docs.py`**:
  - Source: `AGENTS.md` + small per-target tail files in
    `scripts/agent-docs-tails/{claude,copilot,gemini,skill}.md` (the 20%
    tool-specific content).
  - For each target: concatenate `banner + AGENTS.md body + tail`, prepend
    a canonicalised-content SHA256 in the banner so drift is detectable.
  - **Canonicalisation rules** (R1 advisory): LF line endings, single
    trailing newline, YAML keys (for SKILL.md frontmatter) sorted
    alphabetically. Hash inputs only the canonicalised form so editor
    whitespace doesn't cause spurious CI failures.

- **`scripts/check_agent_docs.py`**: runs the sync into a tempdir, diffs
  against the checked-in files, exits nonzero with a clear "regenerate by
  running scripts/sync_agent_docs.py" message on drift.

- **CI**: new `agent-docs` job runs `check_agent_docs.py`. Independent of
  the `test` and `alfred` jobs.

- **CLI**: `screen-harness skill check` is dropped from scope (R1 advisory
  — keep it script-only, no user-facing CLI surface for a dev concern).

- **README** "Use as a Claude Skill" section is rewritten to:
  - List which file each tool reads (with the Copilot opt-in caveat
    spelled out).
  - Point to `AGENTS.md` as the canonical source and to the sync command.

**Out of scope:**

- Publishing to a Skills marketplace.
- Per-target divergence beyond the small tail files.
- A separate Skill bundle zip (Anthropic has not published a publishable
  bundle format yet).

---

## Tests

- Unit: `sync_agent_docs.parse_skill(text)` returns
  `(frontmatter_dict, body_str)` — round-trips a fixture.
- Unit: `render_target("claude" | "copilot" | "skill" | "gemini",
  source, tail)` produces byte-stable golden output (`tests/fixtures/agent_docs/*.expected`).
- Unit: canonicalisation idempotent (`canonicalise(canonicalise(x)) == canonicalise(x)`).
- Unit: SKILL.md `description` length ≤ 1024 enforced (CI fails if exceeded).
- Integration: run sync, then diff against checked-in artefacts; expect
  empty diff in a clean repo.
- CI gate: `agent-docs` job exits 0 on clean repo, nonzero after a manual
  AGENTS.md edit without regeneration (verified by deliberately stale
  fixture branch in tests).

---

## Risks

- **AGENTS.md spec evolution**: the LF AAF spec is young (Feb 2026
  formalisation). Mitigation: the format is plain Markdown — no schema to
  pin. If headings or conventions change, edit AGENTS.md normally.
- **Consumer-version skew**: AGENTS.md is harmlessly ignored by tools
  predating native support. README documents the minimum versions that
  read it: Codex CLI ≥ Feb 2026 release, GitHub Copilot Chat (with
  `useInstructionFiles` setting), Cursor ≥ 2026.02, Windsurf ≥ 2026.02,
  Amp ≥ 2026.02, Devin (current).
- **Claude Code adding AGENTS.md support**: when it does, CLAUDE.md becomes
  redundant. Mitigation: the sync script makes deletion trivial.
- **Copilot setting opt-in is per-user**: documented in the generated
  banner. Not a blocker but users must be told.
- **Anthropic Skills schema evolution**: pinned to the published Anthropic
  Skills docs as of 2026-05; bump CHANGELOG on schema bump.

---

## Acceptance

- `python scripts/sync_agent_docs.py` regenerates AGENTS.md (unchanged),
  CLAUDE.md, `.github/copilot-instructions.md`, SKILL.md; `git diff` empty
  after a fresh edit cycle.
- `python scripts/check_agent_docs.py` returns 0 on clean repo.
- Editing `AGENTS.md` without re-running sync causes CI `agent-docs` to
  fail with a clear "regen needed" message.
- README documents the four-target story with the Copilot opt-in caveat.
- `SKILL.md` validates against Anthropic Skills schema (`description` ≤ 1024 chars).
- No `agent.md` (lowercase) file is shipped.

---

## Change History

| Date | Change | By |
|------|--------|----|
| 2026-05-11 | R1 — Initial proposal (SKILL.md as source — REJECTED, wrong layering) | Claude Code |
| 2026-05-11 | R2 — Re-architect after R1 + web research: AGENTS.md is the LF AAF source of truth; CLAUDE.md + copilot-instructions.md + GEMINI.md (opt) are thin stubs; SKILL.md is the orthogonal Anthropic Skill bundle (name+description schema, ≤1024 chars). Drop agent.md (no consumer). Drop skill-check CLI (dev-only script). Canonicalisation rules for hash stability. Copilot opt-in caveat in banner. | Claude Code |
| 2026-05-11 | R2.1 — Address DeepSeek R2 advisory: pin minimum consumer versions (Codex CLI ≥ Feb 2026 release, Cursor/Windsurf/Amp ≥ 2026.02) in Risks. | Claude Code |
