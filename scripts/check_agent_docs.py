#!/usr/bin/env python3
"""Verify that generated agent-doc files are in sync with their sources.

Runs the sync into a tempdir and diffs against the checked-in files.
Exits 0 on clean, exits 1 with an actionable message on any drift.

Usage:
    python scripts/check_agent_docs.py
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

GENERATED_FILES = [
    REPO_ROOT / "CLAUDE.md",
    REPO_ROOT / ".github" / "copilot-instructions.md",
    REPO_ROOT / "SKILL.md",
]


def _load_sync():
    spec = importlib.util.spec_from_file_location(
        "sync_agent_docs", Path(__file__).parent / "sync_agent_docs.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main(repo_root: Path | None = None) -> int:
    sync = _load_sync()

    root = repo_root if repo_root is not None else REPO_ROOT
    agents_path = root / "AGENTS.md"
    tails_dir = root / "scripts" / "agent-docs-tails"
    targets = {
        "claude": root / "CLAUDE.md",
        "copilot": root / ".github" / "copilot-instructions.md",
        "skill": root / "SKILL.md",
    }

    agents_text = sync.canonicalise(agents_path.read_text(encoding="utf-8"))

    drifted: list[str] = []

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        for target, output_path in targets.items():
            tail_path = tails_dir / f"{target}.md"
            tail_text = sync.canonicalise(tail_path.read_text(encoding="utf-8"))
            tail_fm, tail_body = sync.parse_tail(tail_path)

            source_text = agents_text + tail_text
            source_hash = sync.compute_source_hash(source_text)

            expected = sync.render_target(
                target, agents_text, tail_fm, tail_body, source_hash
            )

            if output_path.exists():
                actual = output_path.read_text(encoding="utf-8")
            else:
                actual = None

            if actual != expected:
                drifted.append(str(output_path.relative_to(root)))

    if drifted:
        print("Agent-docs drift detected in:", file=sys.stderr)
        for f in drifted:
            print(f"  {f}", file=sys.stderr)
        print(
            "\nRun scripts/sync_agent_docs.py and commit the result.",
            file=sys.stderr,
        )
        return 1

    print("agent-docs: ok (all generated files are in sync)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
