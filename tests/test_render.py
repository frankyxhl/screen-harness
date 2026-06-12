from subprocess import CompletedProcess
from unittest.mock import patch

import pytest

from screen_harness.render import (
    DrawBox,
    StepPanel,
    build_concat_command,
    build_intro_source_command,
    build_render_command,
    render_smoke,
    write_spike_ass,
)


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


def test_build_render_command_emits_frosted_panel_filtergraph(tmp_path):
    source = tmp_path / "raw.mp4"
    ass = tmp_path / "sop.ass"
    output = tmp_path / "final.mp4"
    panel = StepPanel(
        x=64,
        y=730,
        width=1180,
        height=150,
        intervals=[(0.0, 3.0), (3.5, 8.0)],
    )

    cmd = build_render_command(source, ass, output, step_panel=panel)
    filter_arg = cmd[cmd.index("-vf") + 1]

    # Split the base, blur a crop of the same frame, tint, and overlay only
    # during step intervals — then burn the ASS on top.
    assert "split=2[base][src]" in filter_arg
    assert "crop=1180:150:64:730" in filter_arg
    assert "boxblur=24:1" in filter_arg
    assert "0xEEEEEE@0.55" in filter_arg
    assert "overlay=64:730" in filter_arg
    assert "between(t\\,0.000\\,3.000)+between(t\\,3.500\\,8.000)" in filter_arg
    assert "subtitles=filename=" in filter_arg
    # Subtitles run after the panel overlay.
    assert filter_arg.index("overlay=") < filter_arg.index("subtitles=")


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


def test_render_smoke_writes_artifacts_and_returns_render_result(tmp_path):
    work = tmp_path / "spike"
    # subprocess.run is called twice: once to generate the testsrc2 input,
    # once to run the render. Stub both to a successful CompletedProcess.
    ok = CompletedProcess(["ffmpeg"], 0, "ok")
    with patch("screen_harness.render.subprocess.run", return_value=ok) as run:
        result = render_smoke(work, ffmpeg="ffmpeg")
    assert result.returncode == 0
    # The smoke run writes its ASS file to disk before invoking the render.
    assert (work / "sop.ass").exists()
    assert run.call_count == 2


def test_render_smoke_returns_failure_from_source_step(tmp_path):
    fail = CompletedProcess(["ffmpeg"], 5, "lavfi died")
    with patch("screen_harness.render.subprocess.run", return_value=fail) as run:
        result = render_smoke(tmp_path, ffmpeg="ffmpeg")
    # Only the source-generation call ran; render is short-circuited.
    assert run.call_count == 1
    assert result.returncode == 5


def test_build_concat_command_rejects_missing_clips(tmp_path):
    with pytest.raises(ValueError, match="at least two input clips"):
        build_concat_command(tmp_path / "only.mp4", tmp_path / "out.mp4")


def test_build_concat_command_with_audio_normalizes_streams(tmp_path):
    """With audio=True every input audio stream goes through `aformat` to a
    common stereo/48k/fltp layout before concat — silent intro/outro and
    mic-recorded main may otherwise have mismatched layouts that break concat.

    Pad order is critical: FFmpeg's concat filter expects per-segment
    interleaved video+audio pads `[v0][a0][v1][a1]…`. Putting all video pads
    first then all audio pads (`[v0][v1][a0][a1]`) compiles but mis-routes
    streams at runtime."""
    intro = tmp_path / "intro.mp4"
    main = tmp_path / "main.mp4"
    output = tmp_path / "final.mp4"

    cmd = build_concat_command(intro, main, output, audio=True)

    filter_arg = cmd[cmd.index("-filter_complex") + 1]
    # Per-input aformat normalisation precedes concat.
    assert "[0:a:0]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[a0]" in filter_arg
    assert "[1:a:0]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[a1]" in filter_arg
    # Interleaved video+audio pad order — NOT [v0][v1][a0][a1].
    assert "[0:v:0][a0][1:v:0][a1]concat=n=2:v=1:a=1[v][a]" in filter_arg
    assert "[0:v:0][1:v:0][a0][a1]" not in filter_arg
    assert "-map" in cmd and "[a]" in cmd
    assert "-c:a" in cmd and cmd[cmd.index("-c:a") + 1] == "aac"


def test_build_concat_command_with_audio_three_clips_keeps_pad_order(tmp_path):
    intro = tmp_path / "intro.mp4"
    main = tmp_path / "main.mp4"
    outro = tmp_path / "outro.mp4"
    output = tmp_path / "final.mp4"

    cmd = build_concat_command(intro, main, outro, output, audio=True)

    filter_arg = cmd[cmd.index("-filter_complex") + 1]
    assert "[0:v:0][a0][1:v:0][a1][2:v:0][a2]concat=n=3:v=1:a=1[v][a]" in filter_arg


def test_build_intro_source_command_with_audio_adds_anullsrc(tmp_path):
    cmd = build_intro_source_command(
        tmp_path / "intro-source.mp4",
        width=1920,
        height=1080,
        fps=30.0,
        duration=4.0,
        background_color="0x222831",
        with_audio=True,
    )

    # Two -i inputs: the color source plus an anullsrc audio source.
    inputs = [cmd[i + 1] for i, token in enumerate(cmd) if token == "-i"]
    assert any(token.startswith("color=") for token in inputs)
    assert any(token.startswith("anullsrc=") for token in inputs)
    assert "-c:a" in cmd and cmd[cmd.index("-c:a") + 1] == "aac"


def test_drawbox_rejects_color_with_filtergraph_metachars():
    with pytest.raises(ValueError, match="DrawBox.color"):
        DrawBox(x=0, y=0, width=10, height=10, color="red); drop")


def test_drawbox_rejects_invalid_thickness():
    with pytest.raises(ValueError, match="DrawBox.thickness"):
        DrawBox(x=0, y=0, width=10, height=10, color="red", thickness="extra")


def test_steppanel_rejects_invalid_tint_color():
    with pytest.raises(ValueError, match="StepPanel.tint_color"):
        StepPanel(x=0, y=0, width=100, height=100, intervals=[(0.0, 1.0)], tint_color="0xEE@0.5; drawbox=0:0:9:9:black")


def test_steppanel_rejects_non_positive_dimensions():
    with pytest.raises(ValueError, match="must be positive"):
        StepPanel(x=0, y=0, width=0, height=10, intervals=[(0.0, 1.0)])


def test_build_intro_source_command_rejects_bg_color_with_metachars(tmp_path):
    with pytest.raises(ValueError, match="background_color"):
        build_intro_source_command(
            tmp_path / "src.mp4",
            width=320,
            height=180,
            fps=30.0,
            duration=1.0,
            background_color="white;rm -rf /",
        )


def test_steppanel_rejects_non_int_dimensions():
    with pytest.raises(ValueError, match="must be int"):
        StepPanel(x=0.5, y=0, width=100, height=100, intervals=[(0.0, 1.0)])  # type: ignore[arg-type]


def test_drawbox_accepts_named_color_with_alpha():
    box = DrawBox(x=0, y=0, width=10, height=10, color="red@0.45", thickness="fill")
    assert box.color == "red@0.45"


def test_ass_escape_neutralizes_brace_injection():
    from screen_harness.render import _ass_escape

    payload = "Innocent {\\fs200}OWNED{\\b0}"
    escaped = _ass_escape(payload)

    assert "\\{" in escaped and "\\}" in escaped
    # The literal \fs200 string (ASCII backslash + 'fs200') survives but is
    # safely contained — no unescaped { or } remain to terminate an override.
    assert "{" not in escaped.replace("\\{", "")
    assert "}" not in escaped.replace("\\}", "")


def test_build_concat_command_supports_intro_main_outro(tmp_path):
    intro = tmp_path / "intro.mp4"
    main = tmp_path / "main.mp4"
    outro = tmp_path / "outro.mp4"
    output = tmp_path / "final.mp4"

    cmd = build_concat_command(intro, main, outro, output)

    filter_arg = cmd[cmd.index("-filter_complex") + 1]
    assert "[0:v:0][1:v:0][2:v:0]concat=n=3:v=1:a=0[v]" in filter_arg
    assert str(output) == cmd[-1]
