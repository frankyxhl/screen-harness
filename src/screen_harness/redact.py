"""Sensitive-text suggestion scanning for transcript and timeline text."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .metadata import update_ai_metadata, write_text_atomic
from .timeline import Timeline, local_now


EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
SECRET_RE = re.compile(r"(?i)\b(?:api[_-]?key|token|secret|password)\s*[:=]\s*([A-Za-z0-9][A-Za-z0-9_.\-]{7,})")
OPENAI_KEY_RE = re.compile(r"\bsk-[A-Za-z0-9_-]{10,}\b")


@dataclass(frozen=True)
class RedactionScanOutputs:
    suggestions: Path
    suggestion_count: int


def scan_redactions(recording_dir: Path) -> RedactionScanOutputs:
    recording_dir = Path(recording_dir)
    suggestions = []
    seen = set()
    next_id = 1
    for item in _text_sources(recording_dir):
        for kind, text, confidence in _matches(item["text"]):
            key = (kind, text, item.get("start"), item.get("end"))
            if key in seen:
                continue
            seen.add(key)
            suggestions.append(
                {
                    "id": f"redact_{next_id:03d}",
                    "type": kind,
                    "text": text,
                    "source": item["source"],
                    "start": item.get("start"),
                    "end": item.get("end"),
                    "confidence": confidence,
                    "reason": f"Potential {kind} in {item['source']}",
                }
            )
            next_id += 1

    output = recording_dir / "redaction_suggestions.json"
    payload = {
        "recording_id": recording_dir.name,
        "created_at": local_now().isoformat(),
        "suggestions": suggestions,
    }
    write_text_atomic(output, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    update_ai_metadata(
        recording_dir,
        "redaction_scan",
        {
            "provider": "regex-local",
            "model": "sensitive-text-patterns-v1",
            "source_inputs": _available_sources(recording_dir),
            "outputs": ["redaction_suggestions.json"],
            "suggestion_count": len(suggestions),
            "generated_at": payload["created_at"],
        },
    )
    return RedactionScanOutputs(suggestions=output, suggestion_count=len(suggestions))


def _text_sources(recording_dir: Path) -> list[dict]:
    sources = []
    transcript_path = recording_dir / "transcript.json"
    if transcript_path.exists():
        payload = json.loads(transcript_path.read_text())
        for segment in payload.get("segments", []):
            sources.append(
                {
                    "source": "transcript",
                    "text": str(segment.get("text", "")),
                    "start": segment.get("start"),
                    "end": segment.get("end"),
                }
            )
    timeline_path = recording_dir / "timeline.json"
    if timeline_path.exists():
        timeline = Timeline.load(timeline_path)
        for event in timeline.data.get("events", []):
            text = event.get("text") or event.get("title") or ""
            if text:
                sources.append(
                    {
                        "source": f"timeline:{event.get('type', 'event')}",
                        "text": str(text),
                        "start": event.get("t"),
                        "end": float(event.get("t", 0.0)) + float(event.get("duration", 0.0)),
                    }
                )
    return sources


def _matches(text: str) -> list[tuple[str, str, str]]:
    matches: list[tuple[str, str, str]] = []
    matches.extend(("email", match.group(0), "high") for match in EMAIL_RE.finditer(text))
    matches.extend(("secret", _trim_secret(match.group(1)), "medium") for match in SECRET_RE.finditer(text))
    matches.extend(("secret", _trim_secret(match.group(0)), "high") for match in OPENAI_KEY_RE.finditer(text))
    return matches


def _available_sources(recording_dir: Path) -> list[str]:
    return [name for name in ("transcript.json", "timeline.json") if (recording_dir / name).exists()]


def _trim_secret(value: str) -> str:
    return value.rstrip(".,;:)]}")
