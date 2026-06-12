"""SOP caption generation from transcript and timeline context."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .captions import CaptionOutputs, generate_caption_assets
from .metadata import update_ai_metadata
from .timeline import Timeline, local_now
from .transcribe import TranscriptSegment


@dataclass(frozen=True)
class SopGenerationOutputs:
    captions: CaptionOutputs
    generated_caption_count: int


FILLER_RE = re.compile(r"\b(?:um+|uh+|er+|ah+|you know|basically)\b[,\s]*", re.IGNORECASE)
LEADING_FILLER_RE = re.compile(r"^\s*(?:so|okay|ok|now|just)\b[,\s]*", re.IGNORECASE)


def generate_ai_sop(recording_dir: Path) -> SopGenerationOutputs:
    """Generate editable SOP captions by writing ai-sop events into timeline.json."""
    recording_dir = Path(recording_dir)
    transcript_path = recording_dir / "transcript.json"
    if not transcript_path.exists():
        raise FileNotFoundError("transcript.json missing; run screen-harness transcribe <recording_id> first")
    segments = load_transcript_segments(transcript_path)
    timeline = Timeline.load(recording_dir / "timeline.json")
    events = [event for event in timeline.data.get("events", []) if event.get("source") != "ai-sop"]
    next_id = _next_event_number(events)
    steps = sorted([event for event in events if event.get("type") == "step"], key=lambda item: float(item.get("t", 0.0)))

    generated = []
    for index, segment in enumerate(segments, start=1):
        text = clean_sop_caption(segment.text)
        if not text:
            continue
        event = {
            "id": f"evt_{next_id:03d}",
            "t": round(segment.start, 3),
            "type": "caption",
            "text": text,
            "duration": round(max(1.0, segment.end - segment.start), 3),
            "source": "ai-sop",
            "transcript_segment": index,
        }
        step_context = _active_step_title(steps, segment.start)
        if step_context:
            event["step_context"] = step_context
        generated.append(event)
        next_id += 1

    timeline.data["events"] = sorted(events + generated, key=lambda event: (float(event.get("t", 0.0)), event.get("id", "")))
    timeline.save()
    outputs = generate_caption_assets(recording_dir)
    update_ai_metadata(
        recording_dir,
        "sop_generation",
        {
            "provider": "heuristic-local",
            "model": "transcript-cleaner-v1",
            "source_inputs": ["transcript.json", "timeline.json"],
            "outputs": ["sop.srt", "sop.ass", "sop.md"],
            "generated_caption_count": len(generated),
            "generated_at": local_now().isoformat(),
        },
    )
    return SopGenerationOutputs(captions=outputs, generated_caption_count=len(generated))


def load_transcript_segments(path: Path) -> list[TranscriptSegment]:
    payload = json.loads(Path(path).read_text())
    segments = []
    for item in payload.get("segments", []):
        segments.append(TranscriptSegment(start=float(item["start"]), end=float(item["end"]), text=str(item["text"])))
    return segments


def clean_sop_caption(text: str) -> str:
    cleaned = text.strip()
    cleaned = FILLER_RE.sub("", cleaned)
    cleaned = LEADING_FILLER_RE.sub("", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,")
    if not cleaned:
        return ""
    cleaned = cleaned[0].upper() + cleaned[1:]
    if cleaned[-1] not in ".!?":
        cleaned += "."
    return cleaned


def _active_step_title(steps: list[dict], start: float) -> str | None:
    active = None
    for step in steps:
        if float(step.get("t", 0.0)) <= start:
            active = str(step.get("title", ""))
        else:
            break
    return active or None


def _next_event_number(events: list[dict]) -> int:
    highest = 0
    for event in events:
        match = re.match(r"evt_(\d+)$", str(event.get("id", "")))
        if match:
            highest = max(highest, int(match.group(1)))
    return highest + 1
