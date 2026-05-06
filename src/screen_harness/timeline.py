"""Timeline JSON model."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


TOKYO = ZoneInfo("Asia/Tokyo")


@dataclass
class Timeline:
    path: Path
    data: dict

    @classmethod
    def create(cls, *, path: Path, recording_id: str, title: str, source_video: str) -> "Timeline":
        data = {
            "recording_id": recording_id,
            "title": title,
            "created_at": datetime.now(TOKYO).isoformat(),
            "source_video": source_video,
            "events": [],
        }
        timeline = cls(Path(path), data)
        timeline.save()
        return timeline

    @classmethod
    def load(cls, path: Path) -> "Timeline":
        path = Path(path)
        return cls(path, json.loads(path.read_text()))

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
