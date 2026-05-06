import pytest

from screen_harness.templates import UnknownTemplateError, get_template


def test_get_template_returns_builtin_templates():
    assert get_template("debug").name == "debug"
    assert get_template("training").name == "training"


def test_get_template_rejects_unknown_template():
    with pytest.raises(UnknownTemplateError, match="unknown render template"):
        get_template("cinema")


def test_training_ass_uses_numbered_lower_corner_step_cards():
    template = get_template("training")
    data = {
        "title": "Demo",
        "events": [
            {"id": "evt_001", "t": 0.0, "type": "chapter", "title": "Setup"},
            {"id": "evt_002", "t": 1.0, "type": "step", "title": "Open Safari", "note": "Launch the browser and prepare to visit the repository"},
            {"id": "evt_003", "t": 4.0, "type": "step", "title": "Visit repository", "note": ""},
        ],
    }

    ass = template.main_ass_text(data)

    assert "Style: StepCard" in ass
    assert "Alignment" in ass
    # Step text positions itself with \an7\pos so the panel stays a fixed width.
    assert "{\\an7\\pos(" in ass
    # Teal accent #00ADB5 for the number, charcoal #222831 for the title.
    assert "{\\b1\\fs44\\c&HB5AD00&}01" in ass
    assert "{\\b1\\fs44\\c&H312822&}Open Safari" in ass
    # Graphite note row #393E46.
    assert "{\\b0\\fs28\\c&H463E39&}Launch the browser and prepare to visit the repository" in ass
    assert "{\\b1\\fs44\\c&H312822&}Visit repository" in ass
    assert "Setup" not in ass
    assert "Dialogue: 0,0:00:01.00,0:00:03." in ass


def test_training_intro_ass_contains_countdown_and_title():
    template = get_template("training")
    data = {
        "title": "Fallback Title",
        "intro": {
            "title": "This video demonstrates Screen Harness",
            "subtitle": "Open Safari and visit the project repository",
            "countdown": 5,
        },
        "events": [],
    }

    ass = template.intro_ass_text(data)

    assert ass is not None
    assert "This video demonstrates Screen Harness" in ass
    assert "Open Safari and visit the project repository" in ass
    for digit in ["5", "4", "3", "2", "1"]:
        assert f",{digit}" in ass
    assert template.intro_duration(data) == 7.0


def test_training_intro_countdown_zero_disables_intro():
    template = get_template("training")
    data = {"title": "Demo", "intro": {"title": "Demo", "countdown": 0}, "events": []}

    assert template.intro_ass_text(data) is None
    assert template.intro_duration(data) == 0.0


def test_training_without_intro_still_renders_step_cards():
    template = get_template("training")
    data = {
        "title": "Demo",
        "events": [{"id": "evt_001", "t": 0.0, "type": "step", "title": "Open Safari"}],
    }

    assert template.intro_ass_text(data) is None
    assert template.intro_duration(data) == 0.0
    assert "{\\b1\\fs44\\c&H312822&}Open Safari" in template.main_ass_text(data)


def test_training_step_panel_rect_anchors_to_bottom_left():
    template = get_template("training")

    rect = template.step_panel_rect((1920, 1080))

    assert rect is not None
    x, y, w, h = rect
    assert x == 64
    assert w == 1180
    assert h == 150
    # Panel sits 50 px above the bottom edge.
    assert y == 1080 - 150 - 50


def test_training_step_panel_rect_returns_none_for_tiny_canvas():
    """The 320x180 e2e fixture would have produced ph=150 inside h=180 — the
    rect must instead return None on canvases that can't host the panel."""
    template = get_template("training")

    # height (180) is enough for the panel (150) + bottom margin (50) → 200, so
    # ph clamps and the rect should be None.
    assert template.step_panel_rect((320, 180)) is None
    # width too narrow.
    assert template.step_panel_rect((100, 1080)) is None
    # Comfortably above the threshold.
    assert template.step_panel_rect((1280, 720)) is not None


def test_training_main_ass_text_omits_step_dialogues_when_panel_does_not_fit():
    template = get_template("training")
    data = {
        "title": "Tiny",
        "events": [{"id": "evt_001", "t": 0.0, "type": "step", "title": "Open"}],
    }
    ass = template.main_ass_text(data, canvas=(320, 180))
    assert "[Events]" in ass
    # No step dialogue lines emitted when the panel can't fit.
    assert "Dialogue:" not in ass


def test_training_outro_duration_rejects_non_numeric():
    template = get_template("training")
    data = {"outro": {"duration": "later"}}
    with pytest.raises(ValueError, match="must be numeric"):
        template.outro_duration(data)


def test_training_outro_renders_url_and_thanks_card():
    template = get_template("training")
    data = {
        "title": "Demo",
        "outro": {
            "title": "Thanks for watching",
            "subtitle": "Find Screen Harness on GitHub",
            "url": "github.com/frankyxhl/screen-harness",
            "duration": 4.0,
        },
        "events": [],
    }

    ass = template.outro_ass_text(data)

    assert ass is not None
    assert "Thanks for watching" in ass
    assert "Find Screen Harness on GitHub" in ass
    assert "github.com/frankyxhl/screen-harness" in ass
    # Wordmark + Title + Subtitle + Link styles all present.
    assert "Style: Wordmark" in ass
    assert "Style: OutroTitle" in ass
    assert "Style: OutroLink" in ass
    assert template.outro_duration(data) == 4.0
    assert template.outro_background_color(data) == "0x222831"


def test_training_outro_disabled_without_outro_field():
    template = get_template("training")
    data = {"title": "Demo", "events": []}

    assert template.outro_ass_text(data) is None
    assert template.outro_duration(data) == 0.0


def test_training_step_intervals_match_step_events():
    template = get_template("training")
    data = {
        "title": "Demo",
        "events": [
            {"id": "evt_001", "t": 1.0, "type": "step", "title": "First"},
            {"id": "evt_002", "t": 5.0, "type": "step", "title": "Second"},
        ],
    }

    intervals = template.step_intervals(data)

    assert len(intervals) == 2
    assert intervals[0][0] == 1.0
    assert intervals[1][0] == 5.0
