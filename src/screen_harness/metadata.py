"""Metadata helpers for recording-derived artifacts."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .timeline import TOKYO


def update_ai_metadata(recording_dir: Path, section: str, payload: dict[str, Any]) -> dict[str, Any]:
    recording_dir = Path(recording_dir)
    metadata_path = recording_dir / "metadata.json"
    metadata = _read_json(metadata_path)
    metadata.setdefault("recording_id", recording_dir.name)
    ai = metadata.setdefault("ai", {})
    section_payload = dict(payload)
    section_payload.setdefault("updated_at", datetime.now(TOKYO).isoformat())
    ai[section] = section_payload
    write_text_atomic(metadata_path, json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
    return metadata


def write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text)
    tmp.replace(path)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}
