import json
import subprocess

import pytest

from screen_harness.admin import ffmpeg_filters
from screen_harness.helpers import render
from screen_harness.metadata import write_text_atomic
from screen_harness.render import _default_render_ffmpeg
from screen_harness.timeline import Timeline


def test_e2e_training_template_renders_synthetic_video(tmp_path, monkeypatch):
    ffmpeg = _render_ffmpeg_or_skip()
    monkeypatch.setenv("SCREEN_HARNESS_FFMPEG", ffmpeg)
    recording = tmp_path / "recordings" / "synthetic_training_demo"
    recording.mkdir(parents=True)
    raw = recording / "raw.mp4"
    source = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=320x180:rate=15",
            "-t",
            "1",
            "-pix_fmt",
            "yuv420p",
            str(raw),
        ],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if source.returncode != 0:
        pytest.skip(f"ffmpeg synthetic source generation failed: {source.stdout}")

    timeline = Timeline.create(
        path=recording / "timeline.json",
        recording_id="synthetic_training_demo",
        title="Synthetic Training Demo",
        source_video="raw.mp4",
        intro={"title": "This video demonstrates the synthetic render path", "countdown": 1},
    )
    timeline.add_event("step", t=0.0, title="Render training template", note="Create professional video assets from a timeline.")
    write_text_atomic(
        recording / "metadata.json",
        json.dumps(
            {
                "recording_id": "synthetic_training_demo",
                "raw_video": "raw.mp4",
                "status": "stopped",
                "canvas": {"width": 320, "height": 180, "fps": 15.0},
            },
            indent=2,
        )
        + "\n",
    )

    final = render(recording, template="training")

    metadata = json.loads((recording / "metadata.json").read_text())
    assert final == recording / "final.mp4"
    assert final.exists()
    assert final.stat().st_size > 0
    assert metadata["render_template"] == "training"
    assert metadata["rendered_video"] == "final.mp4"


def _render_ffmpeg_or_skip() -> str:
    ffmpeg = _default_render_ffmpeg()
    try:
        filters = ffmpeg_filters(ffmpeg)
    except (OSError, subprocess.SubprocessError) as exc:
        pytest.skip(f"ffmpeg unavailable for render e2e: {exc}")
    if not ({"subtitles", "drawbox"}.issubset(filters) or {"ass", "drawbox"}.issubset(filters)):
        pytest.skip("ffmpeg lacks ASS/subtitles and drawbox filters")
    return ffmpeg
