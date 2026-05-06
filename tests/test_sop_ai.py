import json

import pytest

from screen_harness.sop import clean_sop_caption, generate_ai_sop
from screen_harness.timeline import Timeline


def test_clean_sop_caption_removes_fillers_and_adds_period():
    assert clean_sop_caption("um okay open the expense app") == "Open the expense app."


def test_generate_ai_sop_adds_generated_captions_and_provenance(tmp_path):
    timeline = Timeline.create(
        path=tmp_path / "timeline.json",
        recording_id="demo_20260506_120000",
        title="Expense Demo",
        source_video="raw.mp4",
    )
    timeline.add_event("step", t=1.0, title="Open expense app")
    (tmp_path / "metadata.json").write_text(json.dumps({"recording_id": "demo_20260506_120000"}))
    (tmp_path / "transcript.json").write_text(
        json.dumps(
            {
                "segments": [
                    {"start": 1.2, "end": 3.4, "text": "um okay open the expense app"},
                    {"start": 4.0, "end": 6.0, "text": "then submit it"},
                ]
            }
        )
    )

    outputs = generate_ai_sop(tmp_path)

    assert outputs.generated_caption_count == 2
    assert "Open the expense app." in outputs.captions.srt.read_text()
    assert "Then submit it." in outputs.captions.ass.read_text()
    data = json.loads((tmp_path / "timeline.json").read_text())
    generated = [event for event in data["events"] if event.get("source") == "ai-sop"]
    assert generated[0]["step_context"] == "Open expense app"
    metadata = json.loads((tmp_path / "metadata.json").read_text())
    assert metadata["ai"]["sop_generation"]["provider"] == "heuristic-local"
    assert metadata["ai"]["sop_generation"]["generated_caption_count"] == 2


def test_generate_ai_sop_requires_explicit_transcript(tmp_path):
    Timeline.create(path=tmp_path / "timeline.json", recording_id="demo", title="Demo", source_video="raw.mp4")

    with pytest.raises(FileNotFoundError, match="run screen-harness transcribe"):
        generate_ai_sop(tmp_path)


def test_generate_ai_sop_is_idempotent(tmp_path):
    Timeline.create(path=tmp_path / "timeline.json", recording_id="demo", title="Demo", source_video="raw.mp4")
    (tmp_path / "transcript.json").write_text(
        json.dumps(
            {
                "segments": [
                    {"start": 1.0, "end": 3.0, "text": "open the app"},
                    {"start": 3.0, "end": 5.0, "text": "then submit"},
                ]
            }
        )
    )

    generate_ai_sop(tmp_path)
    generate_ai_sop(tmp_path)

    data = json.loads((tmp_path / "timeline.json").read_text())
    generated = [event for event in data["events"] if event.get("source") == "ai-sop"]
    assert len(generated) == 2
