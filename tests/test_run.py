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


def test_render_command_accepts_template_option(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    recording = tmp_path / "recordings" / "demo"
    recording.mkdir(parents=True)

    with patch("screen_harness.run.helper_api.render", return_value=recording / "final.mp4") as render:
        with patch.object(sys, "argv", ["screen-harness", "render", "demo", "--template", "training"]):
            run.main()

    render.assert_called_once_with(recording, template="training")


def test_help_output_lists_commands(capsys):
    with patch.object(sys, "argv", ["screen-harness", "--help"]):
        run.main()

    out = capsys.readouterr().out
    assert "screen-harness doctor" in out
    assert "screen-harness render" in out
    assert "screen-harness sop ai-generate" in out


def test_doctor_command_exits_with_run_doctor_status():
    with patch("screen_harness.run.run_doctor", return_value=0):
        with patch.object(sys, "argv", ["screen-harness", "doctor"]):
            with pytest.raises(SystemExit) as exc:
                run.main()
    assert exc.value.code == 0


def test_init_command_initializes_project(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with patch("screen_harness.run.init_project") as init:
        with patch.object(sys, "argv", ["screen-harness", "init"]):
            run.main()
    init.assert_called_once_with(tmp_path)
    assert "initialized screen-harness workspace" in capsys.readouterr().out


def test_dash_c_without_script_argument_errors():
    with patch.object(sys, "argv", ["screen-harness", "-c"]):
        with pytest.raises(SystemExit, match="Usage: screen-harness -c"):
            run.main()


def test_sop_generate_command_dispatches(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    recording = tmp_path / "recordings" / "demo"
    recording.mkdir(parents=True)

    with patch("screen_harness.run.generate_caption_assets") as captions:
        captions.return_value.markdown = recording / "sop.md"
        with patch.object(sys, "argv", ["screen-harness", "sop", "generate", "demo"]):
            run.main()

    captions.assert_called_once_with(recording)
    assert "sop.md" in capsys.readouterr().out


def test_sop_ai_generate_surfaces_missing_transcript(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    recording = tmp_path / "recordings" / "demo"
    recording.mkdir(parents=True)

    with patch("screen_harness.run.generate_ai_sop", side_effect=FileNotFoundError("no transcript")):
        with patch.object(sys, "argv", ["screen-harness", "sop", "ai-generate", "demo"]):
            with pytest.raises(SystemExit, match="no transcript"):
                run.main()


def test_helpers_open_prints_path(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with patch.object(sys, "argv", ["screen-harness", "helpers", "open"]):
        run.main()

    assert str(tmp_path / "agent-workspace" / "agent_helpers.py") in capsys.readouterr().out


def test_helpers_reset_writes_default_helpers(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with patch.object(sys, "argv", ["screen-harness", "helpers", "reset"]):
        run.main()
    helpers_file = tmp_path / "agent-workspace" / "agent_helpers.py"
    assert helpers_file.exists()
    assert "reset agent_helpers.py" in capsys.readouterr().out


def test_helpers_diff_emits_unified_diff(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    # Initialise then mutate the file so diff has content to emit.
    with patch.object(sys, "argv", ["screen-harness", "helpers", "reset"]):
        run.main()
    capsys.readouterr()  # flush
    helpers_file = tmp_path / "agent-workspace" / "agent_helpers.py"
    helpers_file.write_text(helpers_file.read_text() + "\n# user customization\n")

    with patch.object(sys, "argv", ["screen-harness", "helpers", "diff"]):
        run.main()
    out = capsys.readouterr().out
    assert "user customization" in out


def test_spike_render_smoke_runs_with_returncode(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    work_dir = tmp_path / "spike"
    fake_result = type("R", (), {"returncode": 0, "stdout": "ok\n"})()
    with patch("screen_harness.run.render_smoke", return_value=fake_result) as smoke:
        with patch.object(sys, "argv", ["screen-harness", "spike", "render-smoke", str(work_dir)]):
            with pytest.raises(SystemExit) as exc:
                run.main()
    smoke.assert_called_once_with(work_dir)
    assert exc.value.code == 0


def test_spike_record_runs_with_returncode(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    output = tmp_path / "out.mp4"
    fake_result = type("R", (), {"returncode": 0, "stdout": "ok\n"})()
    with patch("screen_harness.run.record_screen", return_value=fake_result) as record:
        with patch.object(sys, "argv", ["screen-harness", "spike", "record", str(output), "5"]):
            with pytest.raises(SystemExit) as exc:
                run.main()
    record.assert_called_once_with(output, duration=5.0)
    assert exc.value.code == 0


def test_unknown_command_falls_through_to_help():
    with patch.object(sys, "argv", ["screen-harness", "bogus"]):
        with pytest.raises(SystemExit) as exc:
            run.main()
    assert "screen-harness doctor" in str(exc.value)


def test_template_arg_returns_none_when_unspecified():
    assert run._template_arg([]) is None


def test_template_arg_rejects_unknown_flag():
    with pytest.raises(SystemExit, match="--template"):
        run._template_arg(["--bogus", "training"])


def test_provider_arg_rejects_unknown_flag():
    with pytest.raises(SystemExit, match="--provider"):
        run._provider_arg(["--bogus", "manual"])


def test_recording_dir_accepts_existing_relative_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    nested = tmp_path / "alt" / "demo"
    nested.mkdir(parents=True)
    assert run._recording_dir(str(nested)) == nested


def test_render_with_corrupt_timeline_exits_cleanly(tmp_path, monkeypatch):
    """A hand-edited, broken timeline.json must produce a one-line error
    (SystemExit), not a JSONDecodeError traceback."""
    monkeypatch.chdir(tmp_path)
    recording = tmp_path / "recordings" / "demo"
    recording.mkdir(parents=True)
    (recording / "raw.mp4").write_bytes(b"video")
    (recording / "metadata.json").write_text(
        '{"canvas": {"width": 1920, "height": 1080, "fps": 30.0}}'
    )
    (recording / "timeline.json").write_text('{"events": [,]}')

    with patch.object(sys, "argv", ["screen-harness", "render", "demo"]):
        with pytest.raises(SystemExit, match="not valid JSON"):
            run.main()
