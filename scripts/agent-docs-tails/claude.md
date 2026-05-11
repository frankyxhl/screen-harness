## Claude Code notes

Claude Code reads this file. Full agent guidance lives in `AGENTS.md`.
See also `SKILL.md` for the on-demand Anthropic Skill bundle.

**Slash commands** available in this repo:

- `/commit` — creates a conventional commit with co-author attribution.

**Recommended skills** for work in this repo:

- `superpowers:test-driven-development` — for new behavior (RED → GREEN → REFACTOR).
- `superpowers:verification-before-completion` — before claiming done.

**Alfred SOP routing**: run `af guide` at session start to route to the
correct SOPs in `rules/`.

**Reusable helpers**: project-specific Python utilities belong in
`agent-workspace/agent_helpers.py` — they are auto-loaded into every
`screen-harness -c` script namespace.
