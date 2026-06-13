"""Built-in render templates."""

from __future__ import annotations

from dataclasses import dataclass
import textwrap
from typing import Protocol

from screen_harness.render import _ass_escape, _ass_time


class UnknownTemplateError(ValueError):
    """Raised when a render template is not registered."""


# Module-level constants must be defined before any class body that references
# them via f-strings — even though method bodies resolve names lazily, declaring
# them here keeps `TrainingTemplate` instantiation safe even if a future
# refactor moves a constant into a class default.
DEFAULT_FONT = "PingFang SC"
DEFAULT_OUTRO_TITLE = "Thanks for watching"
STEP_NOTE_WIDTH = 60
STEP_PANEL_WIDTH = 1180
STEP_PANEL_HEIGHT = 150
STEP_PANEL_MARGIN_X = 64
STEP_PANEL_MARGIN_BOTTOM = 50
STEP_PANEL_PAD_X = 32
STEP_PANEL_PAD_Y = 24


class RenderTemplate(Protocol):
    name: str

    def main_ass_text(self, data: dict, canvas: tuple[int, int] | None = None) -> str:
        """Return the main recording ASS text."""
        ...

    def intro_ass_text(self, data: dict) -> str | None:
        """Return optional intro ASS text."""
        ...

    def intro_duration(self, data: dict) -> float:
        """Return optional intro pre-roll duration in seconds."""
        ...

    def intro_background_color(self, data: dict) -> str:
        """Return the FFmpeg lavfi color for the intro background."""
        ...

    def step_panel_rect(self, canvas: tuple[int, int]) -> tuple[int, int, int, int] | None:
        """Return (x, y, w, h) of the frosted-glass step panel, if any."""
        ...

    def step_intervals(self, data: dict) -> list[tuple[float, float]]:
        """Return time intervals during which the step panel should be visible."""
        ...

    def outro_ass_text(self, data: dict) -> str | None:
        """Return optional outro ASS text shown after the main recording."""
        ...

    def outro_duration(self, data: dict) -> float:
        """Return optional outro hold duration in seconds."""
        ...

    def outro_background_color(self, data: dict) -> str:
        """Return the FFmpeg lavfi color for the outro background."""
        ...


@dataclass(frozen=True)
class DebugTemplate(RenderTemplate):
    name: str = "debug"

    def main_ass_text(self, data: dict, canvas: tuple[int, int] | None = None) -> str:
        raise NotImplementedError("debug template uses the legacy ASS renderer")

    def intro_ass_text(self, data: dict) -> str | None:
        return None

    def intro_duration(self, data: dict) -> float:
        return 0.0

    def intro_background_color(self, data: dict) -> str:
        return "white"

    def step_panel_rect(self, canvas: tuple[int, int]) -> tuple[int, int, int, int] | None:
        return None

    def step_intervals(self, data: dict) -> list[tuple[float, float]]:
        return []

    def outro_ass_text(self, data: dict) -> str | None:
        return None

    def outro_duration(self, data: dict) -> float:
        return 0.0

    def outro_background_color(self, data: dict) -> str:
        return "white"


@dataclass(frozen=True)
class TrainingTemplate(RenderTemplate):
    """DevDark palette, fixed-position frosted-glass step card.

    Color Hunt "DevDark": `#222831 / #393E46 / #00ADB5 / #EEEEEE`. ASS colors
    use BGR (`&HAABBGGRR`, alpha `00` = visible). Step text is positioned via
    `\\an7\\pos(...)` so the card stays a fixed rectangle regardless of text
    length; the FFmpeg pass paints a frosted-glass panel underneath at the
    same coordinates (see `step_panel_rect`).
    """

    name: str = "training"

    def main_ass_text(self, data: dict, canvas: tuple[int, int] | None = None) -> str:
        canvas_w, canvas_h = canvas or (1920, 1080)
        rect = self.step_panel_rect((canvas_w, canvas_h))
        lines = [
            "[Script Info]",
            f"Title: {_ass_escape(data.get('title', 'Screen Harness SOP'))}",
            "ScriptType: v4.00+",
            "WrapStyle: 0",
            "ScaledBorderAndShadow: yes",
            f"PlayResX: {canvas_w}",
            f"PlayResY: {canvas_h}",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
            # BorderStyle=1 (no opaque box — the FFmpeg blur+tint draws the panel).
            # PrimaryColour: charcoal `#222831` (BGR &H00312822) for legibility on the light frosted panel.
            f"Style: StepCard,{DEFAULT_FONT},34,&H00312822,&H000000FF,&H00FFFFFF,&H00000000,1,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1",
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        ]
        if rect is None:
            # Canvas too small for the step card panel; emit header only so the
            # rendered subtitles file is still valid (no step dialogues).
            return "\n".join(lines) + "\n"
        px, py, _pw, _ph = rect
        steps = _step_events(data)
        text_x = px + STEP_PANEL_PAD_X
        text_y = py + STEP_PANEL_PAD_Y
        for index, event in enumerate(steps, start=1):
            next_event = steps[index] if index < len(steps) else None
            number = int(event.get("number", index))
            title = event.get("title", "Untitled step")
            note = event.get("note")
            text = _step_card_text(number, title, note, anchor=(text_x, text_y))
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
        wordmark = intro.get("wordmark", "SCREEN HARNESS")
        countdown = int(intro.get("countdown", 5))
        duration = self.intro_duration(data)
        # DevDark palette (ASS uses &HAABBGGRR — alpha 00 = visible).
        # Foreground off-white #EEEEEE → &H00EEEEEE
        # Muted teal     #76ABAE       → &H00AEAB76
        # Accent teal    #00ADB5       → &H00B5AD00
        # Surface gray   #393E46       → &H00463E39 (subtle wordmark)
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
            f"Style: Wordmark,{DEFAULT_FONT},26,&H00463E39,&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,8,0,1,0,0,7,96,96,72,1",
            f"Style: IntroTitle,{DEFAULT_FONT},88,&H00EEEEEE,&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,0,0,5,160,160,80,1",
            f"Style: IntroSubtitle,{DEFAULT_FONT},36,&H00AEAB76,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,5,200,200,-40,1",
            f"Style: CountdownLabel,{DEFAULT_FONT},22,&H00463E39,&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,8,0,1,0,0,5,0,0,-280,1",
            f"Style: Countdown,{DEFAULT_FONT},220,&H00B5AD00,&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,0,0,5,0,0,-360,1",
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
            f"Dialogue: 0,0:00:00.00,{_ass_time(duration)},Wordmark,,0,0,0,,{_ass_escape(wordmark)}",
            f"Dialogue: 0,0:00:00.00,{_ass_time(duration)},IntroTitle,,0,0,0,,{_ass_escape(title)}",
        ]
        if subtitle:
            lines.append(f"Dialogue: 0,0:00:00.00,{_ass_time(duration)},IntroSubtitle,,0,0,0,,{_ass_escape(subtitle)}")
        if countdown > 0:
            lines.append(
                f"Dialogue: 0,0:00:01.40,{_ass_time(duration)},CountdownLabel,,0,0,0,,STARTING IN"
            )
        for offset, digit in enumerate(range(countdown, 0, -1), start=2):
            lines.append(f"Dialogue: 0,{_ass_time(offset)},{_ass_time(offset + 1)},Countdown,,0,0,0,,{digit}")
        return "\n".join(lines) + "\n"

    def intro_duration(self, data: dict) -> float:
        intro = data.get("intro") or {}
        countdown = int(intro.get("countdown", 0))
        if countdown <= 0:
            return 0.0
        return float(countdown + 2)

    def intro_background_color(self, data: dict) -> str:
        # Charcoal #222831 — the DevDark base color.
        return "0x222831"

    def step_panel_rect(self, canvas: tuple[int, int]) -> tuple[int, int, int, int] | None:
        """Return (x, y, w, h) of the frosted step panel for a given canvas.

        Returns `None` when the canvas is too small to host the panel — the
        caller (helpers.render) interprets that as "skip the panel filtergraph
        and the step dialogues entirely." Two conditions must hold:

        - Width and height must both be positive after clamping.
        - There must be at least `STEP_PANEL_HEIGHT` of headroom above the
          panel so the recording isn't almost entirely obscured.
        """
        cw, ch = canvas
        pw = min(STEP_PANEL_WIDTH, cw - 2 * STEP_PANEL_MARGIN_X)
        ph = min(STEP_PANEL_HEIGHT, ch - STEP_PANEL_MARGIN_BOTTOM)
        if pw <= 0 or ph <= 0:
            return None
        py = ch - ph - STEP_PANEL_MARGIN_BOTTOM
        if py < STEP_PANEL_HEIGHT:
            return None
        return (STEP_PANEL_MARGIN_X, py, pw, ph)

    def step_intervals(self, data: dict) -> list[tuple[float, float]]:
        steps = _step_events(data)
        result: list[tuple[float, float]] = []
        for index, event in enumerate(steps, start=1):
            next_event = steps[index] if index < len(steps) else None
            result.append((float(event["t"]), float(_step_end(event, next_event))))
        return result

    def outro_ass_text(self, data: dict) -> str | None:
        outro = data.get("outro") or {}
        if not outro:
            return None
        duration = self.outro_duration(data)
        if duration <= 0:
            return None
        title = outro.get("title") or DEFAULT_OUTRO_TITLE
        subtitle = outro.get("subtitle")
        url = outro.get("url")
        wordmark = outro.get("wordmark", "SCREEN HARNESS")
        end = _ass_time(duration)
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
            f"Style: Wordmark,{DEFAULT_FONT},26,&H00463E39,&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,8,0,1,0,0,7,96,96,72,1",
            f"Style: OutroTitle,{DEFAULT_FONT},80,&H00EEEEEE,&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,0,0,5,160,160,140,1",
            f"Style: OutroSubtitle,{DEFAULT_FONT},30,&H00AEAB76,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,5,200,200,40,1",
            f"Style: OutroLink,{DEFAULT_FONT},48,&H00B5AD00,&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,0,0,5,160,160,-160,1",
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
            f"Dialogue: 0,0:00:00.00,{end},Wordmark,,0,0,0,,{_ass_escape(wordmark)}",
            f"Dialogue: 0,0:00:00.20,{end},OutroTitle,,0,0,0,,{_ass_escape(title)}",
        ]
        if subtitle:
            lines.append(f"Dialogue: 0,0:00:00.30,{end},OutroSubtitle,,0,0,0,,{_ass_escape(subtitle)}")
        if url:
            lines.append(f"Dialogue: 0,0:00:00.40,{end},OutroLink,,0,0,0,,{_ass_escape(url)}")
        return "\n".join(lines) + "\n"

    def outro_duration(self, data: dict) -> float:
        outro = data.get("outro") or {}
        if not outro:
            return 0.0
        raw = outro.get("duration", 4.0)
        try:
            return float(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"outro.duration must be numeric, got {raw!r}") from exc

    def outro_background_color(self, data: dict) -> str:
        return "0x222831"


_TEMPLATES: dict[str, RenderTemplate] = {
    "debug": DebugTemplate(),
    "training": TrainingTemplate(),
}


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


def _step_card_text(number: int, title: str, note: str | None, *, anchor: tuple[int, int]) -> str:
    """Render the step card text anchored top-left at `anchor` (DevDark palette).

    DevDark colors (BGR for inline overrides):
      - teal accent  #00ADB5 → &HB5AD00&  (number)
      - charcoal     #222831 → &H312822&  (title)
      - graphite     #393E46 → &H463E39&  (separator dot, note)
      - muted teal   #76ABAE → &HAEAB76&  (alt note tone, kept for fallback)

    All caller-supplied strings (title, note) flow through `_ass_escape`,
    which now also escapes `{` and `}` so they cannot break out of the
    surrounding override blocks.
    """
    ax, ay = anchor
    pos_prefix = f"{{\\an7\\pos({ax},{ay})}}"
    number_chip = f"{{\\b1\\fs44\\c&HB5AD00&}}{number:02d}"
    spacer = "{\\c&H463E39&}  ·  "
    title_text = f"{{\\b1\\fs44\\c&H312822&}}{_ass_escape(title)}"
    head = f"{pos_prefix}{number_chip}{spacer}{title_text}"
    if not note:
        return head
    note_lines = textwrap.wrap(str(note), width=STEP_NOTE_WIDTH, break_long_words=False, break_on_hyphens=False) or [str(note)]
    note_text = "\\N".join(_ass_escape(line) for line in note_lines)
    return f"{head}\\N{{\\b0\\fs28\\c&H463E39&}}{note_text}"
