"""Built-in render templates."""

from __future__ import annotations

from dataclasses import dataclass
import textwrap
from typing import Protocol

from screen_harness.render import _ass_escape, _ass_time


class UnknownTemplateError(ValueError):
    """Raised when a render template is not registered."""


class RenderTemplate(Protocol):
    name: str

    def main_ass_text(self, data: dict) -> str:
        """Return the main recording ASS text."""
        ...

    def intro_ass_text(self, data: dict) -> str | None:
        """Return optional intro ASS text."""
        ...

    def intro_duration(self, data: dict) -> float:
        """Return optional intro pre-roll duration in seconds."""
        ...


@dataclass(frozen=True)
class DebugTemplate:
    name: str = "debug"

    def main_ass_text(self, data: dict) -> str:
        raise NotImplementedError("debug template uses the legacy ASS renderer")

    def intro_ass_text(self, data: dict) -> str | None:
        return None

    def intro_duration(self, data: dict) -> float:
        return 0.0


@dataclass(frozen=True)
class TrainingTemplate:
    name: str = "training"

    def main_ass_text(self, data: dict) -> str:
        lines = [
            "[Script Info]",
            f"Title: {_ass_escape(data.get('title', 'Screen Harness SOP'))}",
            "ScriptType: v4.00+",
            "WrapStyle: 0",
            "ScaledBorderAndShadow: yes",
            "PlayResX: 1920",
            "PlayResY: 1080",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
            f"Style: StepCard,{DEFAULT_FONT},36,&H0025201B,&H000000FF,&H00FFFFFF,&H20F8F8F8,1,0,0,0,100,100,0,0,3,1,0,1,72,72,136,1",
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        ]
        steps = _step_events(data)
        for index, event in enumerate(steps, start=1):
            next_event = steps[index] if index < len(steps) else None
            number = int(event.get("number", index))
            title = f"{number:02d}  {event.get('title', 'Untitled step')}"
            note = event.get("note")
            text = _step_card_text(title, note)
            lines.append(
                f"Dialogue: 0,{_ass_time(event['t'])},{_ass_time(_step_end(event, next_event))},StepCard,,0,0,0,,{text}"
            )
        return "\n".join(lines) + "\n"

    def intro_ass_text(self, data: dict) -> str | None:
        if self.intro_duration(data) <= 0:
            return None
        intro = data.get("intro") or {}
        title = intro.get("title") or data.get("title") or "Screen Harness Demo"
        subtitle = intro.get("subtitle")
        countdown = int(intro.get("countdown", 5))
        duration = self.intro_duration(data)
        lines = [
            "[Script Info]",
            f"Title: {_ass_escape(title)}",
            "ScriptType: v4.00+",
            "WrapStyle: 0",
            "ScaledBorderAndShadow: yes",
            "PlayResX: 1920",
            "PlayResY: 1080",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
            f"Style: IntroTitle,{DEFAULT_FONT},58,&H000000D0,&H000000FF,&H00FFFFFF,&H00FFFFFF,1,0,0,0,100,100,0,0,1,0,0,5,140,140,180,1",
            f"Style: IntroSubtitle,{DEFAULT_FONT},34,&H00303030,&H000000FF,&H00FFFFFF,&H00FFFFFF,0,0,0,0,100,100,0,0,1,0,0,5,160,160,260,1",
            f"Style: Countdown,{DEFAULT_FONT},96,&H000000D0,&H000000FF,&H00FFFFFF,&H00FFFFFF,1,0,0,0,100,100,0,0,1,0,0,5,0,0,360,1",
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
            f"Dialogue: 0,0:00:00.00,{_ass_time(duration)},IntroTitle,,0,0,0,,{_ass_escape(title)}",
        ]
        if subtitle:
            lines.append(f"Dialogue: 0,0:00:00.00,{_ass_time(duration)},IntroSubtitle,,0,0,0,,{_ass_escape(subtitle)}")
        for offset, digit in enumerate(range(countdown, 0, -1), start=2):
            lines.append(f"Dialogue: 0,{_ass_time(offset)},{_ass_time(offset + 1)},Countdown,,0,0,0,,{digit}")
        return "\n".join(lines) + "\n"

    def intro_duration(self, data: dict) -> float:
        intro = data.get("intro") or {}
        countdown = int(intro.get("countdown", 0))
        if countdown <= 0:
            return 0.0
        return float(countdown + 2)


_TEMPLATES: dict[str, RenderTemplate] = {
    "debug": DebugTemplate(),
    "training": TrainingTemplate(),
}

DEFAULT_FONT = "PingFang SC"
STEP_NOTE_WIDTH = 60


def get_template(name: str | None) -> RenderTemplate:
    template_name = name or "debug"
    try:
        return _TEMPLATES[template_name]
    except KeyError as exc:
        raise UnknownTemplateError(f"unknown render template: {template_name}") from exc


def _step_events(data: dict) -> list[dict]:
    events = [event for event in data.get("events", []) if event.get("type") == "step"]
    return sorted(events, key=lambda event: (float(event["t"]), event.get("id", "")))


def _step_end(event: dict, next_event: dict | None) -> float:
    start = float(event["t"])
    default_end = start + float(event.get("duration", 4.0))
    if next_event is None:
        return default_end
    return max(start + 0.5, min(default_end, float(next_event["t"]) - 0.2))


def _step_card_text(title: str, note: str | None) -> str:
    title_text = f"{{\\b1\\fs40}}{_ass_escape(title)}"
    if not note:
        return title_text
    note_lines = textwrap.wrap(str(note), width=STEP_NOTE_WIDTH, break_long_words=False, break_on_hyphens=False) or [str(note)]
    note_text = "\\N".join(_ass_escape(line) for line in note_lines)
    return f"{title_text}\\N{{\\b0\\fs34}}{note_text}"
