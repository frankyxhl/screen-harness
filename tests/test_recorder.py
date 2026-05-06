from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from screen_harness.recorder import build_screen_record_command, record_screen


def test_build_screen_record_command_uses_avfoundation_screen():
    output = Path("recordings/demo/raw.mp4")

    cmd = build_screen_record_command(output, duration=30, screen_index="0")

    assert cmd[:4] == ["ffmpeg", "-y", "-f", "avfoundation"]
    assert "-framerate" in cmd
    assert "30" in cmd
    assert ["-i", "0:none"] == [cmd[cmd.index("-i")], cmd[cmd.index("-i") + 1]]
    assert ["-r", "30"] == [cmd[cmd.index("-r")], cmd[cmd.index("-r") + 1]]
    assert str(output) == cmd[-1]


def test_build_screen_record_command_can_include_audio():
    output = Path("recordings/demo/raw.mp4")

    cmd = build_screen_record_command(output, duration=5, screen_index="0", audio_index="1")

    assert ["-i", "0:1"] == [cmd[cmd.index("-i")], cmd[cmd.index("-i") + 1]]
    assert ["-t", "5"] == [cmd[cmd.index("-t")], cmd[cmd.index("-t") + 1]]


def test_record_screen_fails_if_output_is_missing(tmp_path):
    output = tmp_path / "raw.mp4"

    with patch("screen_harness.recorder.subprocess.run", return_value=CompletedProcess(["ffmpeg"], 0, "ok")):
        result = record_screen(output, duration=1)

    assert result.returncode == 1
    assert "did not create a non-empty output file" in result.stdout
