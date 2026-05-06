import json
from unittest.mock import patch

from screen_harness.transcribe import extract_audio, parse_manual_transcript, transcribe_recording


def test_parse_manual_transcript_supports_timed_and_plain_lines():
    segments = parse_manual_transcript(
        """
        [00:00:01.000 --> 00:00:03.000] Open the expense system
        Submit the form
        """
    )

    assert segments[0].start == 1.0
    assert segments[0].end == 3.0
    assert segments[0].text == "Open the expense system"
    assert segments[1].start == 3.0
    assert segments[1].end == 7.0


def test_transcribe_recording_writes_srt_json_and_metadata(tmp_path):
    recording = tmp_path
    (recording / "raw.mp4").write_bytes(b"not a real mp4")
    (recording / "metadata.json").write_text(json.dumps({"recording_id": "demo"}))
    (recording / "manual_transcript.txt").write_text("00:00:01.000 --> 00:00:03.000 Open expense app\n")

    with patch("screen_harness.transcribe._probe_audio", return_value=(False, "no audio stream")):
        outputs = transcribe_recording(recording)

    assert outputs.segment_count == 1
    assert outputs.audio is None
    assert "00:00:01,000 --> 00:00:03,000" in outputs.transcript_srt.read_text()
    payload = json.loads(outputs.transcript_json.read_text())
    assert payload["provider"] == "manual"
    assert payload["source"] == "manual_transcript.txt"
    metadata = json.loads((recording / "metadata.json").read_text())
    assert metadata["ai"]["transcription"]["provider"] == "manual"
    assert metadata["ai"]["transcription"]["segment_count"] == 1


def test_extract_audio_returns_no_audio_when_stream_missing(tmp_path):
    recording = tmp_path
    (recording / "raw.mp4").write_bytes(b"not a real mp4")

    with patch("screen_harness.transcribe._probe_audio", return_value=(False, "no audio stream")):
        result = extract_audio(recording)

    assert result.audio_stream_found is False
    assert result.extracted is False
    assert result.reason == "no audio stream"
