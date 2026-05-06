import pytest
from unittest.mock import patch

from screen_harness import helpers
from screen_harness.helpers import load_agent_helpers


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


def test_probe_canvas_returns_none_when_ffprobe_missing(tmp_path):
    video = tmp_path / "raw.mp4"
    video.write_bytes(b"not really video")

    with patch("screen_harness.helpers.subprocess.run", side_effect=OSError("missing ffprobe")):
        assert helpers._probe_canvas(video) is None
