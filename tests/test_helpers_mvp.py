import json
import pytest
from unittest.mock import patch

from screen_harness import helpers
from screen_harness.helpers import load_agent_helpers


class DummyProcess:
    stdin = None
    returncode = 0

    def wait(self, timeout=None):
        return 0

    def terminate(self):
        return None

    def kill(self):
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
    helpers.Timeline.create(path=recording / "timeline.json", recording_id="demo", title="Demo", source_video="raw.mp4")
    state = helpers.RuntimeState(root=tmp_path, recording_dir=recording)
    monkeypatch.setattr(helpers, "_STATE", state)

    outputs = helpers.CaptionOutputs(srt=recording / "sop.srt", ass=recording / "sop.ass", markdown=recording / "sop.md")
    with patch("screen_harness.helpers.generate_caption_assets", return_value=outputs) as captions, \
         patch("screen_harness.helpers.render_video") as render_video:
        render_video.return_value.returncode = 0
        render_video.return_value.stdout = ""

        assert helpers.render(template="training") == recording / "final.mp4"

    captions.assert_called_once_with(recording, template="training")


def test_probe_canvas_returns_none_when_ffprobe_missing(tmp_path):
    video = tmp_path / "raw.mp4"
    video.write_bytes(b"not really video")

    with patch("screen_harness.helpers.subprocess.run", side_effect=OSError("missing ffprobe")):
        assert helpers._probe_canvas(video) is None
