from screen_harness.captions import generate_caption_assets
from screen_harness.timeline import Timeline


def test_bdd_training_template_creates_professional_video_assets(tmp_path):
    timeline = Timeline.create(
        path=tmp_path / "timeline.json",
        recording_id="safari_demo",
        title="Safari GitHub Demo",
        source_video="raw.mp4",
        intro={
            "title": "This video demonstrates the Screen Harness GitHub repository",
            "subtitle": "Open Safari and inspect the project page.",
            "countdown": 5,
        },
    )
    timeline.add_event("chapter", t=0.0, title="Repository walkthrough")
    timeline.add_event("step", t=1.0, title="Open Safari", note="Launch the browser in a clean window.")
    timeline.add_event("step", t=4.0, title="Visit repository", note="Open the Screen Harness repository on GitHub.")
    timeline.add_event("caption", t=1.2, text="Open Safari and navigate to the repository.", duration=3.0)

    outputs = generate_caption_assets(tmp_path, template="training")

    intro_ass = outputs.intro_ass.read_text()
    main_ass = outputs.ass.read_text()
    markdown = outputs.markdown.read_text()
    assert "This video demonstrates the Screen Harness GitHub repository" in intro_ass
    assert "5" in intro_ass and "1" in intro_ass
    assert "{\\b1\\fs44\\c&HB5AD00&}01" in main_ass
    assert "{\\b1\\fs44\\c&H312822&}Open Safari" in main_ass
    assert "Launch the browser in a clean window." in main_ass
    assert "{\\b1\\fs44\\c&HB5AD00&}02" in main_ass
    assert "{\\b1\\fs44\\c&H312822&}Visit repository" in main_ass
    assert "Repository walkthrough" not in main_ass
    assert "# Safari GitHub Demo" in markdown
