---
description: Record macOS screen workflows and turn them into SOP videos and Markdown documents. Captures an immutable raw.mp4 + editable timeline.json, then renders an intro card, frosted-glass step overlays, teal highlight strokes, and an outro card with the project URL — all from one Python script.
name: screen-harness
---
<!-- GENERATED FROM AGENTS.md + scripts/agent-docs-tails/skill.md
     Source SHA256: 59f06eebc22c6023f0ed130f8e0e13a79b95ec63fba8e8a523b4f4846719d1be
     Edit AGENTS.md (or the tail file) and run scripts/sync_agent_docs.py. -->

See [AGENTS.md](AGENTS.md) for full agent instructions.

## When to invoke this skill

- The user wants to record a workflow on macOS (a process tour, a bug
  reproduction, a feature demo) and end up with a polished video + Markdown.
- The user mentions Screen Harness, `screen-harness`, `expense_sop.py`,
  `timeline.json`, "training template", or asks about recording into the
  `recordings/` directory.
- The user wants to add an intro, step cards, callouts, or a branded outro
  to an existing recording without re-shooting.

Do **not** use this skill for live transcription / streaming, multi-display
recording, or anything requiring a persistent background daemon.
