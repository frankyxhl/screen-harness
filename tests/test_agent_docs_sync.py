"""Unit tests for scripts/sync_agent_docs.py pure functions.

Fixture layout:
    tests/fixtures/agent_docs/
        source_agents.md
        tail_claude.md
        tail_copilot.md
        tail_skill.md          (WITH YAML frontmatter)
        expected_claude.md
        expected_copilot.md
        expected_skill.md
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures" / "agent_docs"
SCRIPTS = Path(__file__).parent.parent / "scripts"


def load_sync_module():
    spec = importlib.util.spec_from_file_location(
        "sync_agent_docs", SCRIPTS / "sync_agent_docs.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sync = load_sync_module()


# ---------------------------------------------------------------------------
# test_parse_tail_frontmatter_roundtrip
# ---------------------------------------------------------------------------

def test_parse_tail_frontmatter_roundtrip():
    """parse_tail on tail_skill.md → recombine → byte-equal to original file."""
    path = FIXTURES / "tail_skill.md"
    original = sync.canonicalise(path.read_text(encoding="utf-8"))
    fm, body = sync.parse_tail(path)

    assert fm == {"name": "screen-harness", "description": "Record macOS screen workflows and turn them into SOP videos and Markdown documents."}
    # Recombine: emit frontmatter + body
    recombined = sync.emit_frontmatter(fm) + body
    assert sync.canonicalise(recombined) == original


# ---------------------------------------------------------------------------
# test_canonicalise_idempotent
# ---------------------------------------------------------------------------

def test_canonicalise_idempotent():
    text = "line one\nline two\n\n\n"
    assert sync.canonicalise(sync.canonicalise(text)) == sync.canonicalise(text)


# ---------------------------------------------------------------------------
# test_canonicalise_normalises_line_endings
# ---------------------------------------------------------------------------

def test_canonicalise_normalises_line_endings():
    crlf = "line one\r\nline two\r\n"
    result = sync.canonicalise(crlf)
    assert "\r" not in result
    assert result == "line one\nline two\n"


# ---------------------------------------------------------------------------
# test_render_target_claude_matches_expected_fixture
# ---------------------------------------------------------------------------

def test_render_target_claude_matches_expected_fixture():
    agents_text = sync.canonicalise(
        (FIXTURES / "source_agents.md").read_text(encoding="utf-8")
    )
    tail_path = FIXTURES / "tail_claude.md"
    tail_text = sync.canonicalise(tail_path.read_text(encoding="utf-8"))
    tail_fm, tail_body = sync.parse_tail(tail_path)

    source_hash = sync.compute_source_hash(agents_text + tail_text)
    result = sync.render_target("claude", agents_text, tail_fm, tail_body, source_hash)

    expected = (FIXTURES / "expected_claude.md").read_text(encoding="utf-8")
    assert result == expected


# ---------------------------------------------------------------------------
# test_render_target_copilot_matches_expected_fixture
# ---------------------------------------------------------------------------

def test_render_target_copilot_matches_expected_fixture():
    """Also verifies that the opt-in caveat is present in copilot output."""
    agents_text = sync.canonicalise(
        (FIXTURES / "source_agents.md").read_text(encoding="utf-8")
    )
    tail_path = FIXTURES / "tail_copilot.md"
    tail_text = sync.canonicalise(tail_path.read_text(encoding="utf-8"))
    tail_fm, tail_body = sync.parse_tail(tail_path)

    source_hash = sync.compute_source_hash(agents_text + tail_text)
    result = sync.render_target("copilot", agents_text, tail_fm, tail_body, source_hash)

    expected = (FIXTURES / "expected_copilot.md").read_text(encoding="utf-8")
    assert result == expected
    assert "useInstructionFiles" in result


# ---------------------------------------------------------------------------
# test_render_target_skill_emits_sorted_yaml_frontmatter
# ---------------------------------------------------------------------------

def test_render_target_skill_emits_sorted_yaml_frontmatter():
    """SKILL.md output must have description before name (alphabetical order)."""
    agents_text = sync.canonicalise(
        (FIXTURES / "source_agents.md").read_text(encoding="utf-8")
    )
    tail_path = FIXTURES / "tail_skill.md"
    tail_text = sync.canonicalise(tail_path.read_text(encoding="utf-8"))
    tail_fm, tail_body = sync.parse_tail(tail_path)

    source_hash = sync.compute_source_hash(agents_text + tail_text)
    result = sync.render_target("skill", agents_text, tail_fm, tail_body, source_hash)

    lines = result.splitlines()
    assert lines[0] == "<!-- GENERATED FROM AGENTS.md + scripts/agent-docs-tails/skill.md"
    # find the --- block
    fm_start = lines.index("---")
    fm_end = lines.index("---", fm_start + 1)
    fm_lines = lines[fm_start + 1:fm_end]
    keys = [l.split(":")[0].strip() for l in fm_lines]
    assert keys == sorted(keys), f"YAML keys not sorted: {keys}"


# ---------------------------------------------------------------------------
# test_skill_description_too_long_raises
# ---------------------------------------------------------------------------

def test_skill_description_too_long_raises():
    d = {"name": "screen-harness", "description": "x" * 1025}
    with pytest.raises(ValueError, match="description exceeds 1024 chars"):
        sync.emit_frontmatter(d)


# ---------------------------------------------------------------------------
# test_skill_frontmatter_rejects_unknown_keys
# ---------------------------------------------------------------------------

def test_skill_frontmatter_rejects_unknown_keys():
    d = {"name": "screen-harness", "description": "short", "extra": "bad"}
    with pytest.raises(ValueError, match="Unknown frontmatter keys"):
        sync.emit_frontmatter(d)


# ---------------------------------------------------------------------------
# test_yaml_emission_is_byte_stable_across_runs
# ---------------------------------------------------------------------------

def test_yaml_emission_is_byte_stable_across_runs():
    d = {"name": "screen-harness", "description": "A short description."}
    first = sync.emit_frontmatter(d)
    for _ in range(9):
        assert sync.emit_frontmatter(d) == first, "emit_frontmatter is not byte-stable"


# ---------------------------------------------------------------------------
# test_sync_is_idempotent
# ---------------------------------------------------------------------------

def test_sync_is_idempotent(tmp_path):
    """Running render_target twice produces identical output."""
    agents_text = sync.canonicalise(
        (FIXTURES / "source_agents.md").read_text(encoding="utf-8")
    )
    tail_path = FIXTURES / "tail_skill.md"
    tail_text = sync.canonicalise(tail_path.read_text(encoding="utf-8"))
    tail_fm, tail_body = sync.parse_tail(tail_path)

    source_hash = sync.compute_source_hash(agents_text + tail_text)
    run1 = sync.render_target("skill", agents_text, tail_fm, tail_body, source_hash)
    run2 = sync.render_target("skill", agents_text, tail_fm, tail_body, source_hash)
    assert run1 == run2
