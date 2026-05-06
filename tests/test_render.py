from pathlib import Path

from screen_harness.render import DrawBox, build_concat_command, build_intro_source_command, build_render_command, write_spike_ass


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


def test_build_intro_source_command_uses_canvas_and_duration(tmp_path):
    output = tmp_path / "intro-source.mp4"

    cmd = build_intro_source_command(output, width=1920, height=1080, fps=30.0, duration=7.0)

    assert "color=c=white:s=1920x1080:r=30.0:d=7.0" in cmd
    assert "-pix_fmt" in cmd
    assert "yuv420p" in cmd
    assert str(output) == cmd[-1]


def test_build_concat_command_joins_intro_and_main_video(tmp_path):
    intro = tmp_path / "intro.mp4"
    main = tmp_path / "main.mp4"
    output = tmp_path / "final.mp4"

    cmd = build_concat_command(intro, main, output)

    assert str(intro) in cmd
    assert str(main) in cmd
    filter_arg = cmd[cmd.index("-filter_complex") + 1]
    assert "concat=n=2:v=1:a=0" in filter_arg
    assert str(output) == cmd[-1]
