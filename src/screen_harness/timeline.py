"""Timeline JSON model."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


TOKYO = ZoneInfo("Asia/Tokyo")


class TimelineError(Exception):
    """Raised when timeline.json cannot be loaded or fails validation.

    timeline.json is documented as hand-editable ("edit timeline.json and
    re-render"), so load failures must point at the offending field instead
    of surfacing later as a KeyError mid-render.
    """


def _validate_timeline_data(data: object, path: Path) -> dict:
    if not isinstance(data, dict):
        raise TimelineError(
            f"{path}: expected a top-level JSON object, got {type(data).__name__}"
        )
    if "events" not in data:
        raise TimelineError(f"{path}: missing required key 'events'")
    events = data["events"]
    if not isinstance(events, list):
        raise TimelineError(
            f"{path}: 'events' must be a list, got {type(events).__name__}"
        )
    for i, event in enumerate(events):
        if not isinstance(event, dict):
            raise TimelineError(
                f"{path}: events[{i}] must be an object, got {type(event).__name__}"
            )
        if not isinstance(event.get("type"), str):
            raise TimelineError(f"{path}: events[{i}] is missing a string 'type'")
        t = event.get("t")
        if isinstance(t, bool) or not isinstance(t, (int, float)):
            raise TimelineError(
                f"{path}: events[{i}] ({event.get('id', 'no id')}) needs a numeric 't', "
                f"got {t!r}"
            )
    return data


@dataclass
class Timeline:
    path: Path
    data: dict

    @classmethod
    def create(cls, *, path: Path, recording_id: str, title: str, source_video: str, intro: dict | None = None) -> "Timeline":
        data = {
            "recording_id": recording_id,
            "title": title,
            "created_at": datetime.now(TOKYO).isoformat(),
            "source_video": source_video,
            "events": [],
        }
        if intro is not None:
            data["intro"] = intro
        timeline = cls(Path(path), data)
        timeline.save()
        return timeline

    @classmethod
    def load(cls, path: Path) -> "Timeline":
        path = Path(path)
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            raise TimelineError(f"{path}: not valid JSON — {exc}") from exc
        return cls(path, _validate_timeline_data(data, path))

    @staticmethod
    def recording_id(name: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "recording"
        return f"{slug}_{datetime.now(TOKYO).strftime('%Y%m%d_%H%M%S')}"

    def add_event(self, event_type: str, *, t: float, **payload) -> dict:
        event = {"id": f"evt_{len(self.data['events']) + 1:03d}", "t": round(float(t), 3), "type": event_type}
        event.update({k: v for k, v in payload.items() if v is not None})
        self.data["events"].append(event)
        self.save()
        return event

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2) + "\n")
        tmp.replace(self.path)
