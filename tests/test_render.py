from pathlib import Path

from screen_harness.render import DrawBox, build_render_command, write_spike_ass


def test_write_spike_ass_contains_dialogue_and_style(tmp_path):
    ass_path = tmp_path / "sop.ass"

    write_spike_ass(ass_path, title="M0 Spike", caption="Recording pipeline works.", duration=3.0)

    text = ass_path.read_text()
    assert "[Script Info]" in text
    assert "Style: Default" in text
    assert "Dialogue:" in text
    assert "Recording pipeline works." in text


def test_build_render_command_burns_subtitles_and_drawbox(tmp_path):
    source = tmp_path / "raw.mp4"
    ass = tmp_path / "sop.ass"
    output = tmp_path / "final.mp4"

    cmd = build_render_command(
        source,
        ass,
        output,
        boxes=[DrawBox(x=10, y=20, width=100, height=50, start=1.0, duration=2.0)],
    )

    assert cmd[1:3] == ["-y", "-i"]
    assert str(source) in cmd
    filter_arg = cmd[cmd.index("-vf") + 1]
    assert "subtitles=filename=" in filter_arg
    assert "drawbox=" in filter_arg
    assert "between(t\\,1.000\\,3.000)" in filter_arg
    assert str(output) == cmd[-1]
