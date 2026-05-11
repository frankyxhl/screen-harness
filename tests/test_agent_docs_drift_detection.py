"""Integration tests for scripts/check_agent_docs.py drift detection.

These tests run the sync and check functions against a temporary copy of the
repo so the developer's worktree is never mutated during the test run.
"""
from __future__ import annotations

import importlib.util
import io
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
CHECK_SCRIPT = REPO_ROOT / "scripts" / "check_agent_docs.py"
SYNC_SCRIPT = REPO_ROOT / "scripts" / "sync_agent_docs.py"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_test_repo(tmp_path: Path) -> Path:
    """Copy the minimal source set into tmp_path/repo and return that path."""
    repo = tmp_path / "repo"
    repo.mkdir()
    shutil.copy2(REPO_ROOT / "AGENTS.md", repo / "AGENTS.md")
    shutil.copytree(REPO_ROOT / "scripts", repo / "scripts")
    # Copy the currently-generated files so the clean-repo test sees them in sync
    shutil.copy2(REPO_ROOT / "CLAUDE.md", repo / "CLAUDE.md")
    shutil.copy2(REPO_ROOT / "SKILL.md", repo / "SKILL.md")
    (repo / ".github").mkdir()
    shutil.copy2(
        REPO_ROOT / ".github" / "copilot-instructions.md",
        repo / ".github" / "copilot-instructions.md",
    )
    return repo


def test_check_returns_zero_on_clean_repo(tmp_path):
    """After a fresh sync, check_agent_docs.py exits 0."""
    test_repo = _make_test_repo(tmp_path)
    sync = _load_module("sync_agent_docs", SYNC_SCRIPT)
    check = _load_module("check_agent_docs", CHECK_SCRIPT)
    sync.main(repo_root=test_repo)
    result = check.main(repo_root=test_repo)
    assert result == 0, f"Expected exit 0 but got {result}"


def test_check_returns_nonzero_after_manual_edit_to_generated_file(tmp_path):
    """Editing a generated file without re-syncing causes exit 1 with clear message."""
    test_repo = _make_test_repo(tmp_path)
    sync = _load_module("sync_agent_docs", SYNC_SCRIPT)
    check = _load_module("check_agent_docs", CHECK_SCRIPT)
    sync.main(repo_root=test_repo)
    # Append a stray byte to the copy of CLAUDE.md in the temp repo
    claude_md = test_repo / "CLAUDE.md"
    claude_md.write_text(
        claude_md.read_text(encoding="utf-8") + "\n<!-- stray edit -->\n",
        encoding="utf-8",
    )
    captured = io.StringIO()
    old_stderr = sys.stderr
    sys.stderr = captured
    try:
        result = check.main(repo_root=test_repo)
    finally:
        sys.stderr = old_stderr
    assert result == 1
    assert "sync_agent_docs.py" in captured.getvalue()


def test_check_returns_nonzero_after_source_edit_without_resync(tmp_path):
    """Editing AGENTS.md without re-syncing causes exit 1 (real-world failure mode)."""
    test_repo = _make_test_repo(tmp_path)
    sync = _load_module("sync_agent_docs", SYNC_SCRIPT)
    check = _load_module("check_agent_docs", CHECK_SCRIPT)
    sync.main(repo_root=test_repo)
    # Append a stray line to the copy of AGENTS.md in the temp repo
    agents_md = test_repo / "AGENTS.md"
    agents_md.write_text(
        agents_md.read_text(encoding="utf-8") + "\n<!-- source edit without resync -->\n",
        encoding="utf-8",
    )
    captured = io.StringIO()
    old_stderr = sys.stderr
    sys.stderr = captured
    try:
        result = check.main(repo_root=test_repo)
    finally:
        sys.stderr = old_stderr
    assert result == 1
    assert "sync_agent_docs.py" in captured.getvalue()
