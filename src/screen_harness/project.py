"""Project/workspace initialization."""

from __future__ import annotations

from pathlib import Path


DEFAULT_AGENT_HELPERS = '''"""Agent-editable helpers for Screen Harness."""

# Add local workflow helpers here. Public functions are loaded into
# `screen-harness -c` on the next run.
'''


def init_project(root: Path) -> None:
    root = Path(root)
    (root / "recordings").mkdir(parents=True, exist_ok=True)
    workspace = root / "agent-workspace"
    (workspace / "domain-skills").mkdir(parents=True, exist_ok=True)
    (root / "interaction-skills").mkdir(parents=True, exist_ok=True)
    helper_file = workspace / "agent_helpers.py"
    if not helper_file.exists():
        helper_file.write_text(DEFAULT_AGENT_HELPERS)
