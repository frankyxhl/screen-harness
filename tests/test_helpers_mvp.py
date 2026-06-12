import json
import pytest
from unittest.mock import patch

from screen_harness import helpers
from screen_harness.captions import CaptionOutputs
from screen_harness.helpers import load_agent_helpers


class DummyProcess:
    stdin = None
    returncode = 0
    pid = 99999

    def wait(self, timeout=None):
        return 0

    def terminate(self):
        return None

    def kill(self):
        return None

    def send_signal(self, sig):
        return None


def test_load_agent_helpers_adds_public_functions(tmp_path):
    workspace = tmp_path / "agent-workspace"
    workspace.mkdir()
    (workspace / "agent_helpers.py").write_text("def custom_step():\n    return 'loaded'\n")

    namespace = {}
    load_agent_helpers(workspace, namespace)

    assert namespace["custom_step"]() == "loaded"


def test_render_requires_stopped_recording(monkeypatch, tmp_path):
    state = helpers.RuntimeState(root=tmp_path)
    state.recording_dir = tmp_path / "recordings" / "demo"
    state.is_recording = True
    monkeypatch.setattr(helpers, "_STATE", state)

    with pytest.raises(RuntimeError, match="stop_recording"):
        helpers.render()


def test_start_recording_records_cursor_capture_metadata(monkeypatch, tmp_path):
    helpers.configure(tmp_path)

    with patch("screen_harness.helpers.subprocess.Popen", return_value=DummyProcess()), \
         patch("screen_harness.helpers._safe_ffmpeg_version", return_value="ffmpeg version"):
        recording = helpers.start_recording("cursor_demo")

    metadata = json.loads((recording / "metadata.json").read_text())
    assert metadata["capture_cursor"] is True
    assert metadata["capture_mouse_clicks"] is True
    if helpers._STATE.log_handle:
        helpers._STATE.log_handle.close()
    helpers._STATE.is_recording = False


def test_start_recording_threads_region_into_metadata_and_recorder(monkeypatch, tmp_path):
    helpers.configure(tmp_path)
    captured = {}

    def fake_popen(cmd, **kwargs):
        captured["cmd"] = list(cmd)
        return DummyProcess()

    with patch("screen_harness.helpers.subprocess.Popen", side_effect=fake_popen), \
         patch("screen_harness.helpers._safe_ffmpeg_version", return_value="ffmpeg version"):
        recording = helpers.start_recording("region_demo", region=(0, 25, 1920, 1055), hud=False)

    metadata = json.loads((recording / "metadata.json").read_text())
    assert metadata["region"] == [0, 25, 1920, 1055]
    cmd = captured["cmd"]
    vf_index = cmd.index("-vf")
    assert cmd[vf_index + 1] == "crop=1920:1054:0:25"
    if helpers._STATE.log_handle:
        helpers._STATE.log_handle.close()
    helpers._STATE.is_recording = False


def test_intro_and_step_helpers_write_professional_metadata(monkeypatch, tmp_path):
    timeline = helpers.Timeline.create(
        path=tmp_path / "timeline.json",
        recording_id="demo",
        title="Demo",
        source_video="raw.mp4",
    )
    state = helpers.RuntimeState(root=tmp_path, recording_dir=tmp_path, timeline=timeline, started_at=0.0)
    monkeypatch.setattr(helpers, "_STATE", state)
    monkeypatch.setattr(helpers.time, "monotonic", lambda: 2.5)

    helpers.intro("This video demonstrates Screen Harness", subtitle="Open Safari", countdown=5)
    helpers.step("Open Safari", note="Launch the browser", number=1)

    loaded = helpers.Timeline.load(tmp_path / "timeline.json")
    assert loaded.data["intro"]["title"] == "This video demonstrates Screen Harness"
    assert loaded.data["intro"]["subtitle"] == "Open Safari"
    assert loaded.data["intro"]["countdown"] == 5
    assert loaded.data["events"][0]["title"] == "Open Safari"
    assert loaded.data["events"][0]["note"] == "Launch the browser"
    assert loaded.data["events"][0]["number"] == 1


def test_outro_helper_persists_url_and_duration(monkeypatch, tmp_path):
    timeline = helpers.Timeline.create(
        path=tmp_path / "timeline.json",
        recording_id="demo",
        title="Demo",
        source_video="raw.mp4",
    )
    state = helpers.RuntimeState(root=tmp_path, recording_dir=tmp_path, timeline=timeline, started_at=0.0)
    monkeypatch.setattr(helpers, "_STATE", state)

    helpers.outro(
        "Thanks for watching",
        subtitle="Find Screen Harness on GitHub",
        url="github.com/frankyxhl/screen-harness",
        duration=4.5,
    )

    loaded = helpers.Timeline.load(tmp_path / "timeline.json")
    assert loaded.data["outro"]["title"] == "Thanks for watching"
    assert loaded.data["outro"]["subtitle"] == "Find Screen Harness on GitHub"
    assert loaded.data["outro"]["url"] == "github.com/frankyxhl/screen-harness"
    assert loaded.data["outro"]["duration"] == 4.5


def test_outro_helper_rejects_overlong_text(monkeypatch, tmp_path):
    timeline = helpers.Timeline.create(
        path=tmp_path / "timeline.json",
        recording_id="demo",
        title="Demo",
        source_video="raw.mp4",
    )
    state = helpers.RuntimeState(root=tmp_path, recording_dir=tmp_path, timeline=timeline, started_at=0.0)
    monkeypatch.setattr(helpers, "_STATE", state)

    with pytest.raises(ValueError, match="exceeds .* chars"):
        helpers.outro("ok", url="x" * 500)


def test_outro_helper_rejects_control_characters(monkeypatch, tmp_path):
    timeline = helpers.Timeline.create(
        path=tmp_path / "timeline.json",
        recording_id="demo",
        title="Demo",
        source_video="raw.mp4",
    )
    state = helpers.RuntimeState(root=tmp_path, recording_dir=tmp_path, timeline=timeline, started_at=0.0)
    monkeypatch.setattr(helpers, "_STATE", state)

    # C0 control: BEL (0x07).
    with pytest.raises(ValueError, match="control characters"):
        helpers.outro("ok", subtitle="bad\x07subtitle")
    # DEL (0x7F) — outside the original < 0x20 check; now caught via Unicode
    # category Cc.
    with pytest.raises(ValueError, match="control characters"):
        helpers.outro("ok", subtitle="del\x7fhere")
    # C1 control (0x85 = NEL).
    with pytest.raises(ValueError, match="control characters"):
        helpers.outro("ok", subtitle="nel\x85here")


def test_outro_helper_rejects_non_positive_duration(monkeypatch, tmp_path):
    timeline = helpers.Timeline.create(
        path=tmp_path / "timeline.json",
        recording_id="demo",
        title="Demo",
        source_video="raw.mp4",
    )
    state = helpers.RuntimeState(root=tmp_path, recording_dir=tmp_path, timeline=timeline, started_at=0.0)
    monkeypatch.setattr(helpers, "_STATE", state)

    with pytest.raises(ValueError, match="must be positive"):
        helpers.outro("ok", duration=0)


def test_outro_helper_default_uses_template_constant(monkeypatch, tmp_path):
    """Default outro title flows from the same `DEFAULT_OUTRO_TITLE` constant
    the template renders, so the two stay in lock-step."""
    from screen_harness.templates import DEFAULT_OUTRO_TITLE

    timeline = helpers.Timeline.create(
        path=tmp_path / "timeline.json",
        recording_id="demo",
        title="Demo",
        source_video="raw.mp4",
    )
    state = helpers.RuntimeState(root=tmp_path, recording_dir=tmp_path, timeline=timeline, started_at=0.0)
    monkeypatch.setattr(helpers, "_STATE", state)

    helpers.outro()
    loaded = helpers.Timeline.load(tmp_path / "timeline.json")
    assert loaded.data["outro"]["title"] == DEFAULT_OUTRO_TITLE


def test_highlight_region_uses_stronger_default_render_style(monkeypatch, tmp_path):
    timeline = helpers.Timeline.create(
        path=tmp_path / "timeline.json",
        recording_id="demo",
        title="Demo",
        source_video="raw.mp4",
    )
    state = helpers.RuntimeState(root=tmp_path, recording_dir=tmp_path, timeline=timeline, started_at=0.0)
    monkeypatch.setattr(helpers, "_STATE", state)
    monkeypatch.setattr(helpers.time, "monotonic", lambda: 1.0)

    helpers.highlight_region(10, 20, 100, 50, text="Repository header", duration=2.0)

    loaded = helpers.Timeline.load(tmp_path / "timeline.json")
    boxes = helpers._drawboxes(loaded.data)
    assert "color" not in loaded.data["events"][0]
    assert "thickness" not in loaded.data["events"][0]
    assert boxes[0].color == "blue@0.60"
    assert boxes[0].thickness == 10


def test_highlight_region_allows_custom_render_color_and_thickness(monkeypatch, tmp_path):
    timeline = helpers.Timeline.create(
        path=tmp_path / "timeline.json",
        recording_id="demo",
        title="Demo",
        source_video="raw.mp4",
    )
    state = helpers.RuntimeState(root=tmp_path, recording_dir=tmp_path, timeline=timeline, started_at=0.0)
    monkeypatch.setattr(helpers, "_STATE", state)
    monkeypatch.setattr(helpers.time, "monotonic", lambda: 1.0)

    helpers.highlight_region(10, 20, 100, 50, text="Repository header", duration=2.0, color="cyan@0.30", thickness=12)

    loaded = helpers.Timeline.load(tmp_path / "timeline.json")
    boxes = helpers._drawboxes(loaded.data)
    assert loaded.data["events"][0]["color"] == "cyan@0.30"
    assert loaded.data["events"][0]["thickness"] == 12
    assert boxes[0].color == "cyan@0.30"
    assert boxes[0].thickness == 12


def test_render_passes_template_to_caption_generation(monkeypatch, tmp_path):
    recording = tmp_path / "recordings" / "demo"
    recording.mkdir(parents=True)
    (recording / "raw.mp4").write_bytes(b"video")
    # _render_canvas now requires either metadata canvas or a real ffprobe.
    # Seed metadata so the test doesn't depend on either.
    (recording / "metadata.json").write_text(
        '{"canvas": {"width": 1920, "height": 1080, "fps": 30.0}}'
    )
    helpers.Timeline.create(path=recording / "timeline.json", recording_id="demo", title="Demo", source_video="raw.mp4")
    state = helpers.RuntimeState(root=tmp_path, recording_dir=recording)
    monkeypatch.setattr(helpers, "_STATE", state)

    outputs = CaptionOutputs(srt=recording / "sop.srt", ass=recording / "sop.ass", markdown=recording / "sop.md")
    with patch("screen_harness.helpers.generate_caption_assets", return_value=outputs) as captions, \
         patch("screen_harness.helpers.render_video") as render_video, \
         patch("screen_harness.helpers._probe_audio", return_value=False):
        render_video.return_value.returncode = 0
        render_video.return_value.stdout = ""

        assert helpers.render(template="training") == recording / "final.mp4"

    captions.assert_called_once()
    args, kwargs = captions.call_args
    assert args == (recording,)
    assert kwargs["template"] == "training"
    assert kwargs["canvas"] == (1920, 1080)


def test_render_raises_when_canvas_cannot_be_resolved(monkeypatch, tmp_path):
    recording = tmp_path / "recordings" / "demo"
    recording.mkdir(parents=True)
    (recording / "raw.mp4").write_bytes(b"video")
    helpers.Timeline.create(path=recording / "timeline.json", recording_id="demo", title="Demo", source_video="raw.mp4")
    state = helpers.RuntimeState(root=tmp_path, recording_dir=recording)
    monkeypatch.setattr(helpers, "_STATE", state)

    with patch("screen_harness.helpers._probe_canvas", return_value=None):
        with pytest.raises(RuntimeError, match="could not determine canvas"):
            helpers.render(template="training")


def test_render_raises_when_raw_recording_missing(monkeypatch, tmp_path):
    recording = tmp_path / "recordings" / "demo"
    recording.mkdir(parents=True)
    helpers.Timeline.create(path=recording / "timeline.json", recording_id="demo", title="Demo", source_video="raw.mp4")
    state = helpers.RuntimeState(root=tmp_path, recording_dir=recording)
    monkeypatch.setattr(helpers, "_STATE", state)

    with pytest.raises(FileNotFoundError, match="raw recording not found"):
        helpers.render(template="training")


def test_probe_canvas_returns_none_when_ffprobe_missing(tmp_path):
    video = tmp_path / "raw.mp4"
    video.write_bytes(b"not really video")

    with patch("screen_harness.helpers.subprocess.run", side_effect=OSError("missing ffprobe")):
        assert helpers._probe_canvas(video) is None


def test_wait_sleeps_with_supplied_seconds(monkeypatch):
    calls: list[float] = []
    monkeypatch.setattr(helpers.time, "sleep", lambda s: calls.append(s))
    helpers.wait(2.5)
    assert calls == [2.5]


def test_wait_for_user_consumes_input(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda prompt="": "")
    helpers.wait_for_user("ready?")  # no exception => good


def test_wrapper_helpers_dispatch_to_module_functions(monkeypatch, tmp_path):
    recording = tmp_path / "rec"
    recording.mkdir()
    state = helpers.RuntimeState(root=tmp_path, recording_dir=recording)
    monkeypatch.setattr(helpers, "_STATE", state)

    sentinel = object()
    with patch("screen_harness.helpers.generate_caption_assets", return_value=sentinel) as captions:
        assert helpers.generate_sop_captions(template="training") is sentinel
        captions.assert_called_once_with(recording, template="training")

    with patch("screen_harness.helpers.generate_caption_assets") as captions:
        captions.return_value.markdown = recording / "sop.md"
        assert helpers.generate_markdown_sop() == recording / "sop.md"

    with patch("screen_harness.helpers.transcribe_recording", return_value=sentinel) as t:
        assert helpers.transcribe() is sentinel
        t.assert_called_once_with(recording)

    with patch("screen_harness.helpers.scan_recording_redactions", return_value=sentinel) as s:
        assert helpers.scan_redactions() is sentinel
        s.assert_called_once_with(recording)

    with patch("screen_harness.helpers.generate_ai_sop_assets", return_value=sentinel) as g:
        assert helpers.generate_ai_sop() is sentinel
        g.assert_called_once_with(recording)


def test_render_propagates_step_panel_and_outro(monkeypatch, tmp_path):
    recording = tmp_path / "recordings" / "demo"
    recording.mkdir(parents=True)
    (recording / "raw.mp4").write_bytes(b"video")
    timeline = helpers.Timeline.create(
        path=recording / "timeline.json",
        recording_id="demo",
        title="Demo",
        source_video="raw.mp4",
        intro={"title": "Demo", "countdown": 1},
    )
    timeline.add_event("step", t=0.5, title="One")
    timeline.data["outro"] = {"title": "Thanks", "duration": 2.0, "url": "github.com/example"}
    timeline.save()
    state = helpers.RuntimeState(root=tmp_path, recording_dir=recording)
    monkeypatch.setattr(helpers, "_STATE", state)

    fake_result = type("R", (), {"returncode": 0, "stdout": ""})()
    with patch("screen_harness.helpers._probe_canvas", return_value={"width": 1920, "height": 1080, "fps": 30.0}), \
         patch("screen_harness.helpers._probe_audio", return_value=False), \
         patch("screen_harness.helpers.create_intro_source", return_value=fake_result), \
         patch("screen_harness.helpers.render_video", return_value=fake_result) as rv, \
         patch("screen_harness.helpers.concat_videos", return_value=fake_result) as concat:
        helpers.render(template="training")

    # Three render_video calls: intro card + main + outro card.
    assert rv.call_count == 3
    main_call = rv.call_args_list[1]
    panel = main_call.kwargs["step_panel"]
    assert panel is not None
    assert panel.intervals  # at least one interval populated from the step event
    # Concat receives intro + main + outro + final.
    assert len(concat.call_args.args) == 4
    # Audio was not detected on the stub raw, so concat is invoked with audio=False.
    assert concat.call_args.kwargs.get("audio") is False


def test_render_card_clip_raises_on_intro_source_failure(monkeypatch, tmp_path):
    bad_result = type("R", (), {"returncode": 1, "stdout": "lavfi failed"})()
    with patch("screen_harness.helpers.create_intro_source", return_value=bad_result):
        with pytest.raises(RuntimeError, match="lavfi failed"):
            helpers._render_card_clip(
                tmp_path,
                source_name="intro-source.mp4",
                clip_name="intro.mp4",
                ass=tmp_path / "intro.ass",
                canvas={"width": 1920, "height": 1080, "fps": 30.0},
                duration=3.0,
                background_color="0x222831",
            )


def test_simple_event_helpers_append_to_timeline(monkeypatch, tmp_path):
    timeline = helpers.Timeline.create(
        path=tmp_path / "timeline.json",
        recording_id="demo",
        title="Demo",
        source_video="raw.mp4",
    )
    state = helpers.RuntimeState(root=tmp_path, recording_dir=tmp_path, timeline=timeline, started_at=0.0)
    monkeypatch.setattr(helpers, "_STATE", state)
    monkeypatch.setattr(helpers.time, "monotonic", lambda: 5.0)

    helpers.chapter("Setup")
    helpers.click(120, 240, label="OK button")
    helpers.redact_region(10, 20, 100, 50, reason="email")

    events = timeline.data["events"]
    assert events[0]["type"] == "chapter"
    assert events[0]["title"] == "Setup"
    assert events[1]["type"] == "click"
    assert events[1]["x"] == 120 and events[1]["y"] == 240
    assert events[1]["label"] == "OK button"
    assert events[2]["type"] == "redact"
    assert events[2]["rect"] == [10, 20, 100, 50]
    assert events[2]["reason"] == "email"


def test_drawboxes_warns_when_rect_extends_outside_canvas(caplog):
    data = {
        "events": [
            {"id": "1", "t": 0.0, "type": "highlight", "rect": [-50, 0, 100, 100], "text": "Stray"},
        ]
    }
    with caplog.at_level("WARNING", logger="screen_harness"):
        boxes = helpers._drawboxes(data, canvas=(1920, 1080))
    assert len(boxes) == 1
    assert any("extends outside canvas" in record.message for record in caplog.records)


def test_drawboxes_warns_for_click_outside_canvas(caplog):
    data = {"events": [{"id": "c", "t": 0.0, "type": "click", "x": 5000, "y": 5000}]}
    with caplog.at_level("WARNING", logger="screen_harness"):
        helpers._drawboxes(data, canvas=(1920, 1080))
    assert any("outside canvas" in record.message for record in caplog.records)


def test_drawboxes_quiet_when_canvas_is_unknown():
    data = {"events": [{"id": "1", "t": 0.0, "type": "highlight", "rect": [-50, 0, 100, 100]}]}
    # Without a canvas hint we don't warn — caller hasn't asked us to validate.
    boxes = helpers._drawboxes(data, canvas=None)
    assert len(boxes) == 1


def test_probe_audio_warns_when_ffprobe_missing(monkeypatch, tmp_path, caplog):
    raw = tmp_path / "raw.mp4"
    raw.write_bytes(b"video")
    with patch("screen_harness.helpers.subprocess.run", side_effect=OSError("ffprobe gone")):
        with caplog.at_level("WARNING", logger="screen_harness"):
            assert helpers._probe_audio(raw) is False
    assert any("ffprobe unavailable" in record.message for record in caplog.records)


def test_start_recording_uses_new_session_so_kill_signals_group(monkeypatch, tmp_path):
    """start_new_session=True must be passed to Popen so we can kill ffmpeg's
    whole process group on stop/abort."""
    helpers.configure(tmp_path)
    captured: dict = {}

    def fake_popen(cmd, **kwargs):
        captured["kwargs"] = kwargs
        return DummyProcess()

    with patch("screen_harness.helpers.subprocess.Popen", side_effect=fake_popen), \
         patch("screen_harness.helpers._safe_ffmpeg_version", return_value="ffmpeg version"):
        helpers.start_recording("session_demo")

    assert captured["kwargs"].get("start_new_session") is True
    helpers._STATE.is_recording = False
    if helpers._STATE.log_handle:
        helpers._STATE.log_handle.close()


def test_signal_process_group_falls_back_to_send_signal_on_oserror():
    """If killpg can't reach the group (e.g. process already exited), we
    fall back to send_signal so the lifecycle keeps moving."""
    sent: list[int] = []

    class StubProcess:
        pid = 12345

        def send_signal(self, sig):
            sent.append(sig)

    with patch("screen_harness.helpers.os.killpg", side_effect=ProcessLookupError("gone")), \
         patch("screen_harness.helpers.os.getpgid", return_value=12345):
        helpers._signal_process_group(StubProcess(), 15)

    assert sent == [15]


def test_drawboxes_translates_redact_and_click_events():
    data = {
        "events": [
            {"id": "1", "t": 0.0, "type": "redact", "rect": [10, 20, 100, 50], "duration": 2.0},
            {"id": "2", "t": 1.0, "type": "click", "x": 200, "y": 300},
        ]
    }
    boxes = helpers._drawboxes(data)
    assert len(boxes) == 2
    assert boxes[0].thickness == "fill"
    assert boxes[0].color == "black@0.85"
    # Click is translated to a 36x36 marker centered on (200, 300).
    assert boxes[1].x == 200 - 18
    assert boxes[1].y == 300 - 18
    assert boxes[1].width == 36 and boxes[1].height == 36


def test_stop_recording_writes_final_metadata(monkeypatch, tmp_path):
    helpers.configure(tmp_path)
    process = DummyProcess()
    process.stdin = type("S", (), {"write": lambda self, b: None, "flush": lambda self: None})()

    captured: dict = {}

    def fake_popen(cmd, **kwargs):
        captured["cmd"] = list(cmd)
        return process

    with patch("screen_harness.helpers.subprocess.Popen", side_effect=fake_popen), \
         patch("screen_harness.helpers._safe_ffmpeg_version", return_value="ffmpeg version"):
        recording = helpers.start_recording("stop_demo")

    monkeypatch.setattr(helpers, "_elapsed", lambda: 4.2)
    monkeypatch.setattr(helpers, "_probe_canvas", lambda path: {"width": 1920, "height": 1080, "fps": 30.0})

    result = helpers.stop_recording()

    assert result == recording
    metadata = json.loads((recording / "metadata.json").read_text())
    assert metadata["status"] == "stopped"
    assert metadata["duration"] == 4.2
    assert metadata["recording_stopped_at"] is not None
    assert metadata["canvas"]["width"] == 1920
    assert helpers._STATE.is_recording is False


def test_stop_recording_marks_error_when_ffmpeg_fails(monkeypatch, tmp_path):
    helpers.configure(tmp_path)
    failing = DummyProcess()
    failing.stdin = type("S", (), {"write": lambda self, b: None, "flush": lambda self: None})()
    failing.returncode = 7

    with patch("screen_harness.helpers.subprocess.Popen", return_value=failing), \
         patch("screen_harness.helpers._safe_ffmpeg_version", return_value="ffmpeg version"):
        recording = helpers.start_recording("err_demo")

    monkeypatch.setattr(helpers, "_elapsed", lambda: 1.0)
    monkeypatch.setattr(helpers, "_probe_canvas", lambda path: None)

    helpers.stop_recording()
    metadata = json.loads((recording / "metadata.json").read_text())
    assert metadata["status"] == "error"
    assert "ffmpeg exited 7" in metadata["error"]


def test_stop_recording_without_active_recording_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(helpers, "_STATE", helpers.RuntimeState(root=tmp_path))
    with pytest.raises(RuntimeError, match="no active recording"):
        helpers.stop_recording()


def test_stop_recording_clears_state_when_metadata_write_fails(monkeypatch, tmp_path):
    """If the post-FFmpeg metadata write raises, the runtime must still mark
    the recording as no-longer-active and close the log handle, otherwise a
    transient FS error leaves the harness wedged."""
    helpers.configure(tmp_path)
    process = DummyProcess()
    process.stdin = type("S", (), {"write": lambda self, b: None, "flush": lambda self: None})()
    closed: list[bool] = []

    class FakeLog:
        closed_state = False

        def close(self):
            self.closed_state = True
            closed.append(True)

    log = FakeLog()

    with patch("screen_harness.helpers.subprocess.Popen", return_value=process), \
         patch("screen_harness.helpers._safe_ffmpeg_version", return_value="ffmpeg version"):
        recording = helpers.start_recording("fail_demo")
    helpers._STATE.log_handle = log

    # Sabotage the metadata read so stop_recording's body raises mid-flight.
    monkeypatch.setattr(helpers, "_elapsed", lambda: 1.0)
    (recording / "metadata.json").write_text("{not valid json")

    with pytest.raises(json.JSONDecodeError):
        helpers.stop_recording()

    assert helpers._STATE.is_recording is False
    assert closed == [True]


def test_stop_recording_tolerates_stdin_oserror(monkeypatch, tmp_path):
    """A closed/invalid stdin must not abort the wait/terminate cascade — we
    fall through and still finalize metadata cleanly."""
    helpers.configure(tmp_path)
    process = DummyProcess()

    class BadStdin:
        def write(self, b):
            raise OSError("Bad file descriptor")

        def flush(self):
            raise ValueError("flush of closed file")

    process.stdin = BadStdin()

    with patch("screen_harness.helpers.subprocess.Popen", return_value=process), \
         patch("screen_harness.helpers._safe_ffmpeg_version", return_value="ffmpeg version"):
        recording = helpers.start_recording("oserror_demo")

    monkeypatch.setattr(helpers, "_elapsed", lambda: 0.5)
    monkeypatch.setattr(helpers, "_probe_canvas", lambda path: {"width": 1920, "height": 1080, "fps": 30.0})

    helpers.stop_recording()
    metadata = json.loads((recording / "metadata.json").read_text())
    assert metadata["status"] == "stopped"
    assert helpers._STATE.is_recording is False


def test_abort_active_recording_clears_state_when_metadata_write_fails(monkeypatch, tmp_path):
    """If the abort path's metadata write raises, runtime state must still be
    nulled — otherwise a transient FS error wedges the harness into thinking
    a recording is live."""
    recording = tmp_path / "rec"
    recording.mkdir()
    (recording / "metadata.json").write_text("{not valid json")
    process = DummyProcess()
    state = helpers.RuntimeState(
        root=tmp_path,
        recording_dir=recording,
        process=process,
        is_recording=True,
        log_handle=None,
        started_at=0.0,
    )
    monkeypatch.setattr(helpers, "_STATE", state)

    with pytest.raises(json.JSONDecodeError):
        helpers.abort_active_recording()

    assert helpers._STATE.is_recording is False
    assert helpers._STATE.process is None
    assert helpers._STATE.log_handle is None


def test_abort_active_recording_terminates_and_marks_metadata(monkeypatch, tmp_path):
    recording = tmp_path / "rec"
    recording.mkdir()
    metadata = recording / "metadata.json"
    metadata.write_text('{"status": "recording"}')
    process = DummyProcess()
    state = helpers.RuntimeState(
        root=tmp_path,
        recording_dir=recording,
        process=process,
        is_recording=True,
        log_handle=None,
        started_at=0.0,
    )
    monkeypatch.setattr(helpers, "_STATE", state)

    helpers.abort_active_recording()

    import json as _json
    saved = _json.loads(metadata.read_text())
    assert saved["status"] == "aborted"
    assert saved["error"] == "script exited before stop_recording()"
    assert helpers._STATE.is_recording is False
