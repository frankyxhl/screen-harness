import json

from screen_harness.redact import scan_redactions
from screen_harness.timeline import Timeline


def test_scan_redactions_detects_email_and_secret(tmp_path):
    timeline = Timeline.create(path=tmp_path / "timeline.json", recording_id="demo", title="Demo", source_video="raw.mp4")
    timeline.add_event("caption", t=4.0, duration=2.0, text="Use token=sk_test_1234567890 for the sandbox")
    (tmp_path / "metadata.json").write_text(json.dumps({"recording_id": "demo"}))
    (tmp_path / "transcript.json").write_text(
        json.dumps(
            {
                "segments": [
                    {"start": 1.0, "end": 3.0, "text": "Send the request to user@example.com"},
                    {"start": 4.0, "end": 6.0, "text": "Use token=sk_test_1234567890 for the sandbox"},
                ]
            }
        )
    )

    outputs = scan_redactions(tmp_path)

    payload = json.loads(outputs.suggestions.read_text())
    assert outputs.suggestion_count == 2
    assert {item["type"] for item in payload["suggestions"]} == {"email", "secret"}
    assert {item["text"] for item in payload["suggestions"]} == {"user@example.com", "sk_test_1234567890"}
    assert {item["confidence"] for item in payload["suggestions"]} == {"high", "medium"}
    metadata = json.loads((tmp_path / "metadata.json").read_text())
    assert metadata["ai"]["redaction_scan"]["suggestion_count"] == 2


def test_scan_redactions_deduplicates_same_text_at_same_time(tmp_path):
    timeline = Timeline.create(path=tmp_path / "timeline.json", recording_id="demo", title="Demo", source_video="raw.mp4")
    timeline.add_event("caption", t=1.0, duration=2.0, text="Contact user@example.com")
    timeline.add_event("step", t=1.0, duration=2.0, title="Contact user@example.com")
    (tmp_path / "transcript.json").write_text(
        json.dumps({"segments": [{"start": 1.0, "end": 3.0, "text": "Contact user@example.com"}]})
    )

    outputs = scan_redactions(tmp_path)

    payload = json.loads(outputs.suggestions.read_text())
    assert outputs.suggestion_count == 1
    assert payload["suggestions"][0]["text"] == "user@example.com"
