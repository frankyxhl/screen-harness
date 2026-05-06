from screen_harness.timeline import Timeline


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
    timeline.add_event("step", t=0.0, title="Open Chrome", note="Launch the browser", number=1)

    loaded = Timeline.load(tmp_path / "timeline.json")
    assert loaded.data["intro"]["countdown"] == 5
    assert loaded.data["events"][0]["note"] == "Launch the browser"
    assert loaded.data["events"][0]["number"] == 1
