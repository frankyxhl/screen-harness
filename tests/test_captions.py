from screen_harness.captions import generate_caption_assets
from screen_harness.timeline import Timeline


def test_generate_caption_assets_writes_srt_ass_and_markdown(tmp_path):
    timeline = Timeline.create(
        path=tmp_path / "timeline.json",
        recording_id="demo_20260506_120000",
        title="Expense Demo",
        source_video="raw.mp4",
    )
    timeline.add_event("step", t=0.5, title="Open expense system")
    timeline.add_event("caption", t=0.7, text="Open the expense system.", duration=2.0)

    outputs = generate_caption_assets(tmp_path)

    assert outputs.srt.read_text().startswith("1\n00:00:00,700 --> 00:00:02,700")
    assert "Open the expense system." in outputs.ass.read_text()
    md = outputs.markdown.read_text()
    assert "# Expense Demo" in md
    assert "Open expense system" in md


def test_generate_caption_assets_allows_zero_captions(tmp_path):
    Timeline.create(
        path=tmp_path / "timeline.json",
        recording_id="demo_20260506_120000",
        title="Visual Demo",
        source_video="raw.mp4",
    )

    outputs = generate_caption_assets(tmp_path)

    assert outputs.srt.read_text() == ""
    assert "[Events]" in outputs.ass.read_text()
    assert "# Visual Demo" in outputs.markdown.read_text()


def test_generate_caption_assets_debug_template_matches_default(tmp_path):
    timeline = Timeline.create(
        path=tmp_path / "timeline.json",
        recording_id="demo_20260506_120000",
        title="Debug Demo",
        source_video="raw.mp4",
    )
    timeline.add_event("step", t=0.5, title="Open expense system")
    timeline.add_event("caption", t=0.7, text="Open the expense system.", duration=2.0)

    default_outputs = generate_caption_assets(tmp_path)
    default_ass = default_outputs.ass.read_text()
    default_srt = default_outputs.srt.read_text()
    debug_outputs = generate_caption_assets(tmp_path, template="debug")

    assert debug_outputs.ass.read_text() == default_ass
    assert debug_outputs.srt.read_text() == default_srt
    assert debug_outputs.intro_ass is None


def test_generate_caption_assets_writes_training_intro_ass(tmp_path):
    timeline = Timeline.create(
        path=tmp_path / "timeline.json",
        recording_id="demo_20260506_120000",
        title="Safari Demo",
        source_video="raw.mp4",
    )
    timeline.data["intro"] = {"title": "This video demonstrates the GitHub repository", "subtitle": "Open Safari", "countdown": 5}
    timeline.add_event("step", t=1.0, title="Open Safari", note="Launch the browser")

    outputs = generate_caption_assets(tmp_path, template="training")

    assert outputs.intro_ass is not None
    assert "This video demonstrates the GitHub repository" in outputs.intro_ass.read_text()
    assert "01  Open Safari" in outputs.ass.read_text()
