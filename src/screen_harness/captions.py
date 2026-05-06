"""SRT, ASS, and Markdown generation from timeline events."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .metadata import write_text_atomic
from .render import _ass_escape, _ass_time
from .timeline import Timeline


@dataclass(frozen=True)
class CaptionOutputs:
    srt: Path
    ass: Path
    markdown: Path


def generate_caption_assets(recording_dir: Path) -> CaptionOutputs:
    recording_dir = Path(recording_dir)
    timeline = Timeline.load(recording_dir / "timeline.json")
    srt = recording_dir / "sop.srt"
    ass = recording_dir / "sop.ass"
    markdown = recording_dir / "sop.md"
    write_text_atomic(srt, _srt_text(timeline.data["events"]))
    write_text_atomic(ass, _ass_text(timeline.data))
    write_text_atomic(markdown, _markdown_text(timeline.data))
    return CaptionOutputs(srt=srt, ass=ass, markdown=markdown)


def _caption_events(events: list[dict]) -> list[dict]:
    captions = [event for event in events if event["type"] == "caption"]
    return sorted(captions, key=lambda event: (float(event["t"]), event.get("id", "")))


def _caption_end(event: dict, next_event: dict | None) -> float:
    start = float(event["t"])
    default_end = start + float(event.get("duration", 4.0))
    if next_event is None:
        return default_end
    return min(default_end, float(next_event["t"]))


def _srt_text(events: list[dict]) -> str:
    captions = _caption_events(events)
    blocks = []
    for index, event in enumerate(captions, start=1):
        next_event = captions[index] if index < len(captions) else None
        blocks.append(
            f"{index}\n{_srt_time(event['t'])} --> {_srt_time(_caption_end(event, next_event))}\n{event['text']}\n"
        )
    return "\n".join(blocks)


def _ass_text(data: dict) -> str:
    lines = [
        "[Script Info]",
        f"Title: {data.get('title', 'Screen Harness SOP')}",
        "ScriptType: v4.00+",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Default,Arial,36,&H00FFFFFF,&H000000FF,&H7F000000,&H7F000000,0,0,0,0,100,100,0,0,1,2,0,2,40,40,42,1",
        "Style: Step,Arial,34,&H00FFFFFF,&H000000FF,&H7F111111,&H7F111111,1,0,0,0,100,100,0,0,1,2,0,8,40,40,36,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    events = data.get("events", [])
    captions = _caption_events(events)
    for event in events:
        if event["type"] == "step":
            lines.append(
                f"Dialogue: 0,{_ass_time(event['t'])},{_ass_time(float(event['t']) + 3.0)},Step,,0,0,0,,{_ass_escape(event['title'])}"
            )
    for index, event in enumerate(captions):
        next_event = captions[index + 1] if index + 1 < len(captions) else None
        lines.append(
            f"Dialogue: 0,{_ass_time(event['t'])},{_ass_time(_caption_end(event, next_event))},Default,,0,0,0,,{_ass_escape(event['text'])}"
        )
    return "\n".join(lines) + "\n"


def _markdown_text(data: dict) -> str:
    lines = [f"# {data.get('title', data.get('recording_id', 'SOP'))}", ""]
    step_number = 1
    events = data.get("events", [])
    for event in events:
        if event["type"] != "step":
            continue
        lines.append(f"## {step_number}. {event['title']}")
        lines.append("")
        lines.append(f"- Time: {_display_time(event['t'])}")
        caption = _first_caption_after(events, event["t"])
        if caption:
            lines.append(f"- Note: {caption['text']}")
        lines.append("")
        step_number += 1
    if step_number == 1:
        lines.append("No steps recorded.")
        lines.append("")
    return "\n".join(lines)


def _first_caption_after(events: list[dict], t: float) -> dict | None:
    for event in _caption_events(events):
        if float(event["t"]) >= float(t):
            return event
    return None


def _srt_time(seconds: float) -> str:
    milliseconds = int(round(float(seconds) * 1000))
    h, rem = divmod(milliseconds, 3600 * 1000)
    m, rem = divmod(rem, 60 * 1000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _display_time(seconds: float) -> str:
    total = int(float(seconds))
    m, s = divmod(total, 60)
    return f"{m:02d}:{s:02d}"
