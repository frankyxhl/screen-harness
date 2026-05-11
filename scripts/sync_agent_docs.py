#!/usr/bin/env python3
"""Emit CLAUDE.md, .github/copilot-instructions.md, and SKILL.md from AGENTS.md + tail files.

Usage:
    python scripts/sync_agent_docs.py

Run from any directory — paths are resolved relative to the repo root
(the directory containing this script's parent directory).
"""
from __future__ import annotations

import hashlib
from pathlib import Path

# TODO(gemini): read pyproject [tool.screen-harness].gemini and emit GEMINI.md

REPO_ROOT = Path(__file__).parent.parent
TAILS_DIR = Path(__file__).parent / "agent-docs-tails"

TARGETS = {
    "claude": REPO_ROOT / "CLAUDE.md",
    "copilot": REPO_ROOT / ".github" / "copilot-instructions.md",
    "skill": REPO_ROOT / "SKILL.md",
}


def parse_tail(path: Path) -> tuple[dict, str]:
    """Split YAML frontmatter (--- delimited) from body.

    Returns ({}, full_text) if no frontmatter block is present.
    """
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    fm_block = text[4:end]
    body = text[end + 5:]
    frontmatter: dict = {}
    for line in fm_block.splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            frontmatter[key.strip()] = value.strip()
    return frontmatter, body


def canonicalise(text: str) -> str:
    """Normalise to LF line endings and a single trailing newline."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.rstrip("\n") + "\n"
    return text


def emit_frontmatter(d: dict) -> str:
    """Emit a 2-key YAML block (name + description only, alphabetical order).

    Raises ValueError if the dict does not contain exactly {name, description},
    for multi-line values, or description > 1024 chars.
    """
    REQUIRED = {"name", "description"}
    if set(d) != REQUIRED:
        missing = REQUIRED - set(d)
        extras = set(d) - REQUIRED
        msg_parts = []
        if missing:
            msg_parts.append(f"missing keys: {sorted(missing)}")
        if extras:
            msg_parts.append(f"unknown keys: {sorted(extras)}")
        raise ValueError(f"Frontmatter must contain exactly name+description; {'; '.join(msg_parts)}")
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


def compute_source_hash(canonicalised_text: str) -> str:
    """Return SHA256 hex digest (64 chars) of the canonicalised source text."""
    return hashlib.sha256(canonicalised_text.encode("utf-8")).hexdigest()


def build_banner(target: str, source_hash: str) -> str:
    """Return the pinned banner string for the given target and source hash."""
    return (
        f"<!-- GENERATED FROM AGENTS.md + scripts/agent-docs-tails/{target}.md\n"
        f"     Source SHA256: {source_hash}\n"
        f"     Edit AGENTS.md (or the tail file) and run scripts/sync_agent_docs.py. -->\n"
    )


def render_target(
    target: str,
    agents_body: str,
    tail_frontmatter: dict,
    tail_body: str,
    source_hash: str,
) -> str:
    """Assemble the final bytes for a target file.

    For 'skill': emitted YAML frontmatter + banner + AGENTS.md pointer + tail body.
    For 'claude' / 'copilot': banner + AGENTS.md body + tail body.
    """
    banner = build_banner(target, source_hash)
    if target == "skill":
        fm = emit_frontmatter(tail_frontmatter)
        pointer = "\nSee [AGENTS.md](AGENTS.md) for full agent instructions.\n"
        return canonicalise(fm + banner + pointer + tail_body)
    else:
        return canonicalise(banner + agents_body + tail_body)


def main() -> None:
    agents_path = REPO_ROOT / "AGENTS.md"
    agents_text = canonicalise(agents_path.read_text(encoding="utf-8"))

    for target, output_path in TARGETS.items():
        tail_path = TAILS_DIR / f"{target}.md"
        tail_text = canonicalise(tail_path.read_text(encoding="utf-8"))
        tail_frontmatter, tail_body = parse_tail(tail_path)

        source_text = agents_text + tail_text
        source_hash = compute_source_hash(source_text)

        content = render_target(target, agents_text, tail_frontmatter, tail_body, source_hash)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
        print(f"Wrote {output_path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
