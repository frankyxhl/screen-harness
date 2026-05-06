import sys
from unittest.mock import patch

import pytest

from screen_harness import run


def test_cleans_up_active_recording_when_c_script_raises(tmp_path):
    with patch.object(sys, "argv", ["screen-harness", "-c", "raise RuntimeError('boom')"]), \
         patch("screen_harness.run.init_project"), \
         patch("screen_harness.run.helper_api.configure"), \
         patch("screen_harness.run.helper_api.load_agent_helpers"), \
         patch("screen_harness.run.helper_api.abort_active_recording") as abort:
        with pytest.raises(RuntimeError, match="boom"):
            run.main()

    abort.assert_called_once()


def test_recording_dir_prefers_recordings_for_plain_id(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "demo").mkdir()

    assert run._recording_dir("demo") == tmp_path / "recordings" / "demo"


def test_provider_arg_defaults_to_manual():
    assert run._provider_arg([]) == "manual"


def test_provider_arg_accepts_explicit_provider():
    assert run._provider_arg(["--provider", "manual"]) == "manual"


def test_transcribe_command_dispatches(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    recording = tmp_path / "recordings" / "demo"
    recording.mkdir(parents=True)

    with patch("screen_harness.run.transcribe_recording") as transcribe:
        transcribe.return_value.transcript_srt = recording / "transcript.srt"
        with patch.object(sys, "argv", ["screen-harness", "transcribe", "demo", "--provider", "manual"]):
            run.main()

    transcribe.assert_called_once_with(recording, provider_name="manual")


def test_sop_ai_generate_command_dispatches(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    recording = tmp_path / "recordings" / "demo"
    recording.mkdir(parents=True)

    with patch("screen_harness.run.generate_ai_sop") as generate:
        generate.return_value.captions.markdown = recording / "sop.md"
        with patch.object(sys, "argv", ["screen-harness", "sop", "ai-generate", "demo"]):
            run.main()

    generate.assert_called_once_with(recording)


def test_redact_scan_command_dispatches(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    recording = tmp_path / "recordings" / "demo"
    recording.mkdir(parents=True)

    with patch("screen_harness.run.scan_redactions") as scan:
        scan.return_value.suggestions = recording / "redaction_suggestions.json"
        with patch.object(sys, "argv", ["screen-harness", "redact", "scan", "demo"]):
            run.main()

    scan.assert_called_once_with(recording)
