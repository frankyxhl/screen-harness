import pytest

from screen_harness.timeline import Timeline, TimelineError


def test_timeline_adds_events_and_writes_json(tmp_path):
    timeline_path = tmp_path / "timeline.json"
    timeline = Timeline.create(
        path=timeline_path,
        recording_id="demo_20260506_120000",
        title="Demo",
        source_video="raw.mp4",
    )

    timeline.add_event("step", t=1.0, title="Open app")
    timeline.add_event("caption", t=1.2, text="Open the target app.", duration=2.5)

    loaded = Timeline.load(timeline_path)
    assert loaded.data["recording_id"] == "demo_20260506_120000"
    assert loaded.data["events"][0]["id"] == "evt_001"
    assert loaded.data["events"][1]["type"] == "caption"


def test_timeline_recording_id_slug_has_timestamp():
    rid = Timeline.recording_id("Expense Create Request")

    assert rid.startswith("expense_create_request_")
    assert len(rid.rsplit("_", 2)) == 3


def test_timeline_create_accepts_intro_metadata(tmp_path):
    timeline = Timeline.create(
        path=tmp_path / "timeline.json",
        recording_id="demo",
        title="Demo",
        source_video="raw.mp4",
        intro={"title": "This video demonstrates the demo flow", "countdown": 5},
    )
    timeline.add_event("step", t=0.0, title="Open Safari", note="Launch the browser", number=1)

    loaded = Timeline.load(tmp_path / "timeline.json")
    assert loaded.data["intro"]["countdown"] == 5
    assert loaded.data["events"][0]["note"] == "Launch the browser"
    assert loaded.data["events"][0]["number"] == 1


# ---------------------------------------------------------------------------
# Load validation — timeline.json is documented as hand-editable ("edit
# timeline.json and re-render"), so malformed input must fail at load time
# with a message pointing at the problem, not as a KeyError mid-render.


def test_load_rejects_invalid_json(tmp_path):
    path = tmp_path / "timeline.json"
    path.write_text('{"events": [,]}')

    with pytest.raises(TimelineError, match=r"not valid JSON"):
        Timeline.load(path)


def test_load_invalid_json_error_names_the_file(tmp_path):
    path = tmp_path / "timeline.json"
    path.write_text("not json at all")

    with pytest.raises(TimelineError, match=r"timeline\.json"):
        Timeline.load(path)


def test_load_rejects_non_object_top_level(tmp_path):
    path = tmp_path / "timeline.json"
    path.write_text('["just", "a", "list"]')

    with pytest.raises(TimelineError, match=r"top-level JSON object"):
        Timeline.load(path)


def test_load_rejects_missing_events_key(tmp_path):
    path = tmp_path / "timeline.json"
    path.write_text('{"recording_id": "demo", "title": "Demo"}')

    with pytest.raises(TimelineError, match=r"events"):
        Timeline.load(path)


def test_load_rejects_events_not_a_list(tmp_path):
    path = tmp_path / "timeline.json"
    path.write_text('{"events": {"evt_001": {}}}')

    with pytest.raises(TimelineError, match=r"events.*list"):
        Timeline.load(path)


def test_load_rejects_non_dict_event_with_index(tmp_path):
    path = tmp_path / "timeline.json"
    path.write_text('{"events": [{"t": 0.0, "type": "step"}, "oops"]}')

    with pytest.raises(TimelineError, match=r"events\[1\]"):
        Timeline.load(path)


def test_load_rejects_event_missing_type(tmp_path):
    path = tmp_path / "timeline.json"
    path.write_text('{"events": [{"id": "evt_001", "t": 1.5}]}')

    with pytest.raises(TimelineError, match=r"events\[0\].*type"):
        Timeline.load(path)


def test_load_rejects_event_with_non_numeric_t(tmp_path):
    path = tmp_path / "timeline.json"
    path.write_text('{"events": [{"id": "evt_001", "type": "step", "t": "1.5s"}]}')

    with pytest.raises(TimelineError, match=r"events\[0\].*numeric"):
        Timeline.load(path)


def test_load_rejects_event_missing_t(tmp_path):
    path = tmp_path / "timeline.json"
    path.write_text('{"events": [{"id": "evt_001", "type": "step"}]}')

    with pytest.raises(TimelineError, match=r"events\[0\]"):
        Timeline.load(path)


def test_load_accepts_integer_t(tmp_path):
    path = tmp_path / "timeline.json"
    path.write_text('{"events": [{"id": "evt_001", "type": "step", "t": 2}]}')

    loaded = Timeline.load(path)
    assert loaded.data["events"][0]["t"] == 2


def test_load_round_trip_of_created_timeline_still_works(tmp_path):
    path = tmp_path / "timeline.json"
    timeline = Timeline.create(
        path=path, recording_id="demo", title="Demo", source_video="raw.mp4"
    )
    timeline.add_event("step", t=1.0, title="Open app")

    loaded = Timeline.load(path)
    assert loaded.data["events"][0]["title"] == "Open app"
