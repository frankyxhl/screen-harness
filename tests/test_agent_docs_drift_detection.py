"""Integration tests for scripts/check_agent_docs.py drift detection.

These tests run the check script as a subprocess and verify exit codes.
They require that AGENTS.md, SKILL.md, CLAUDE.md, and
.github/copilot-instructions.md are in sync at the time the test runs.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
CHECK_SCRIPT = REPO_ROOT / "scripts" / "check_agent_docs.py"
SYNC_SCRIPT = REPO_ROOT / "scripts" / "sync_agent_docs.py"


def _run_check() -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CHECK_SCRIPT)],
        capture_output=True,
        text=True,
    )


def _run_sync() -> None:
    subprocess.run(
        [sys.executable, str(SYNC_SCRIPT)],
        check=True,
        capture_output=True,
    )


def test_check_returns_zero_on_clean_repo(tmp_path):
    """After a fresh sync, check_agent_docs.py exits 0."""
    _run_sync()
    result = _run_check()
    assert result.returncode == 0, (
        f"Expected exit 0 but got {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_check_returns_nonzero_after_manual_edit_to_generated_file(tmp_path):
    """Editing a generated file without re-syncing causes exit 1 with clear message."""
    _run_sync()
    # Append a stray byte to CLAUDE.md
    claude_md = REPO_ROOT / "CLAUDE.md"
    original = claude_md.read_text(encoding="utf-8")
    try:
        claude_md.write_text(original + "\n<!-- stray edit -->\n", encoding="utf-8")
        result = _run_check()
        assert result.returncode == 1
        assert "sync_agent_docs.py" in result.stdout or "sync_agent_docs.py" in result.stderr
    finally:
        claude_md.write_text(original, encoding="utf-8")


def test_check_returns_nonzero_after_source_edit_without_resync(tmp_path):
    """Editing AGENTS.md without re-syncing causes exit 1 (real-world failure mode)."""
    _run_sync()
    agents_md = REPO_ROOT / "AGENTS.md"
    original = agents_md.read_text(encoding="utf-8")
    try:
        agents_md.write_text(original + "\n<!-- source edit without resync -->\n", encoding="utf-8")
        result = _run_check()
        assert result.returncode == 1
        assert "sync_agent_docs.py" in result.stdout or "sync_agent_docs.py" in result.stderr
    finally:
        agents_md.write_text(original, encoding="utf-8")
