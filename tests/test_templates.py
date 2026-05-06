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
    assert "&H0025201B" in ass
    assert "&H20F8F8F8" in ass
    assert "{\\b1\\fs40}01  Open Safari" in ass
    assert "{\\b0\\fs34}Launch the browser and prepare to visit the repository" in ass
    assert "01  Open Safari" in ass
    assert "Launch the browser and prepare to visit the repository" in ass
    assert "02  Visit repository" in ass
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
    assert "01  Open Safari" in template.main_ass_text(data)
