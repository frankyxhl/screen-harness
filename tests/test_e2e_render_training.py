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


def test_e2e_training_template_appends_outro_when_set(tmp_path, monkeypatch):
    """BDD: when an outro is configured, the rendered final.mp4 is longer than
    main+intro alone — confirming the outro card was concatenated."""
    ffmpeg = _render_ffmpeg_or_skip()
    monkeypatch.setenv("SCREEN_HARNESS_FFMPEG", ffmpeg)
    recording = tmp_path / "recordings" / "synthetic_outro_demo"
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
        recording_id="synthetic_outro_demo",
        title="Synthetic Outro Demo",
        source_video="raw.mp4",
        intro={"title": "Synthetic outro path", "countdown": 1},
    )
    timeline.add_event("step", t=0.0, title="Render with outro")
    timeline.data["outro"] = {
        "title": "Thanks for watching",
        "subtitle": "Find the project on GitHub",
        "url": "github.com/frankyxhl/screen-harness",
        "duration": 2.0,
    }
    timeline.save()
    write_text_atomic(
        recording / "metadata.json",
        json.dumps(
            {
                "recording_id": "synthetic_outro_demo",
                "raw_video": "raw.mp4",
                "status": "stopped",
                "canvas": {"width": 320, "height": 180, "fps": 15.0},
            },
            indent=2,
        )
        + "\n",
    )

    final = render(recording, template="training")

    assert final.exists() and final.stat().st_size > 0
    # outro.ass and outro.mp4 must have been produced.
    assert (recording / "outro.ass").exists()
    assert (recording / "outro.mp4").exists()
    assert (recording / "intro.mp4").exists()
    assert (recording / "main.mp4").exists()
    # Final must be at least as long as main + intro + outro (allow a small tolerance).
    duration = _probe_duration(ffmpeg, final)
    assert duration >= 1.0 + 3.0 + 2.0 - 0.4  # main 1s + intro (countdown+2)=3s + outro 2s


def test_e2e_training_template_renders_panel_at_full_canvas(tmp_path, monkeypatch):
    """BDD: at a canvas large enough to host the step card panel
    (≥ STEP_PANEL_HEIGHT*2 + margin) the rendered final.mp4 must include the
    frosted-glass overlay during the step interval — exercising the
    split/crop/boxblur/overlay filtergraph for real."""
    ffmpeg = _render_ffmpeg_or_skip()
    monkeypatch.setenv("SCREEN_HARNESS_FFMPEG", ffmpeg)
    recording = tmp_path / "recordings" / "panel_demo"
    recording.mkdir(parents=True)
    raw = recording / "raw.mp4"
    source = subprocess.run(
        [
            ffmpeg, "-y", "-f", "lavfi",
            "-i", "testsrc2=size=1280x720:rate=15",
            "-t", "2",
            "-pix_fmt", "yuv420p",
            str(raw),
        ],
        check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    if source.returncode != 0:
        pytest.skip(f"ffmpeg synthetic source generation failed: {source.stdout}")

    timeline = Timeline.create(
        path=recording / "timeline.json",
        recording_id="panel_demo",
        title="Panel demo",
        source_video="raw.mp4",
    )
    timeline.add_event("step", t=0.0, title="Frame the demo", note="Frosted-glass step card test.")
    write_text_atomic(
        recording / "metadata.json",
        json.dumps(
            {"recording_id": "panel_demo", "raw_video": "raw.mp4", "status": "stopped",
             "canvas": {"width": 1280, "height": 720, "fps": 15.0}},
            indent=2,
        ) + "\n",
    )

    final = render(recording, template="training")

    assert final.exists() and final.stat().st_size > 0
    # No intro/outro configured ⇒ final = main only, same duration as raw.
    assert abs(_probe_duration(ffmpeg, final) - 2.0) < 0.4


def _probe_duration(ffmpeg: str, path) -> float:
    from screen_harness.admin import ffprobe_binary

    result = subprocess.run(
        [
            ffprobe_binary(),
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return float(result.stdout.strip() or 0.0)


def _render_ffmpeg_or_skip() -> str:
    ffmpeg = _default_render_ffmpeg()
    try:
        filters = ffmpeg_filters(ffmpeg)
    except (OSError, subprocess.SubprocessError) as exc:
        pytest.skip(f"ffmpeg unavailable for render e2e: {exc}")
    if not ({"subtitles", "drawbox"}.issubset(filters) or {"ass", "drawbox"}.issubset(filters)):
        pytest.skip("ffmpeg lacks ASS/subtitles and drawbox filters")
    return ffmpeg
