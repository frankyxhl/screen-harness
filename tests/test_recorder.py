from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from screen_harness.recorder import build_screen_record_command, record_screen
from screen_harness.screens import ScreenDevice


def _fake_screen(av_index: int = 0) -> ScreenDevice:
    return ScreenDevice(
        av_index=av_index,
        av_name=f"Capture screen {av_index}",
        display_id=12345,
        bounds=(0, 0, 1920, 1080),
        is_main=True,
        backing_scale=2.0,
    )


def test_build_screen_record_command_uses_avfoundation_screen():
    output = Path("recordings/demo/raw.mp4")

    cmd = build_screen_record_command(output, duration=30, screen_device=_fake_screen(0))

    assert cmd[:4] == ["ffmpeg", "-y", "-f", "avfoundation"]
    assert "-framerate" in cmd
    assert "30" in cmd
    assert ["-capture_cursor", "true"] == [cmd[cmd.index("-capture_cursor")], cmd[cmd.index("-capture_cursor") + 1]]
    assert ["-capture_mouse_clicks", "true"] == [cmd[cmd.index("-capture_mouse_clicks")], cmd[cmd.index("-capture_mouse_clicks") + 1]]
    assert ["-i", "0:none"] == [cmd[cmd.index("-i")], cmd[cmd.index("-i") + 1]]
    assert ["-r", "30"] == [cmd[cmd.index("-r")], cmd[cmd.index("-r") + 1]]
    assert str(output) == cmd[-1]


def test_build_screen_record_command_can_include_audio():
    output = Path("recordings/demo/raw.mp4")

    cmd = build_screen_record_command(output, duration=5, screen_device=_fake_screen(0), audio_index="1")

    assert ["-i", "0:1"] == [cmd[cmd.index("-i")], cmd[cmd.index("-i") + 1]]
    assert ["-t", "5"] == [cmd[cmd.index("-t")], cmd[cmd.index("-t") + 1]]


def test_build_screen_record_command_can_disable_cursor_capture():
    output = Path("recordings/demo/raw.mp4")

    cmd = build_screen_record_command(
        output, duration=5, screen_device=_fake_screen(0),
        capture_cursor=False, capture_mouse_clicks=False,
    )

    assert ["-capture_cursor", "false"] == [cmd[cmd.index("-capture_cursor")], cmd[cmd.index("-capture_cursor") + 1]]
    assert ["-capture_mouse_clicks", "false"] == [cmd[cmd.index("-capture_mouse_clicks")], cmd[cmd.index("-capture_mouse_clicks") + 1]]


def test_build_screen_record_command_applies_region_crop():
    output = Path("recordings/demo/raw.mp4")

    cmd = build_screen_record_command(
        output, duration=5, screen_device=_fake_screen(0), region=(0, 25, 1920, 1055),
    )

    # Crop filter must precede -pix_fmt and use even dimensions.
    vf_index = cmd.index("-vf")
    assert cmd[vf_index + 1] == "crop=1920:1054:0:25"
    assert cmd.index("-pix_fmt") > vf_index


def test_build_screen_record_command_omits_crop_without_region():
    output = Path("recordings/demo/raw.mp4")

    cmd = build_screen_record_command(output, duration=5, screen_device=_fake_screen(0))

    assert "-vf" not in cmd


def test_build_screen_record_command_rejects_negative_region_origin():
    import pytest

    with pytest.raises(ValueError, match="non-negative"):
        build_screen_record_command(
            Path("recordings/demo/raw.mp4"),
            duration=5,
            screen_device=_fake_screen(0),
            region=(-10, 0, 1920, 1080),
        )


def test_build_screen_record_command_rejects_zero_region_size():
    import pytest

    with pytest.raises(ValueError, match="positive"):
        build_screen_record_command(
            Path("recordings/demo/raw.mp4"),
            duration=5,
            screen_device=_fake_screen(0),
            region=(0, 0, 0, 1080),
        )


def test_build_screen_record_command_requires_screen_device():
    """Codex P1 round 6: refuse to build a command without a validated ScreenDevice."""
    import pytest

    with pytest.raises(ValueError, match="screen_device is required"):
        build_screen_record_command(Path("recordings/demo/raw.mp4"), duration=5, screen_device=None)


def test_build_screen_record_command_rejects_camera_via_null_display_id():
    """display_id=0 (kCGNullDirectDisplay) means 'not actually a screen'."""
    import pytest

    bad_device = ScreenDevice(
        av_index=0, av_name="FaceTime HD Camera",
        display_id=0,  # camera sentinel
        bounds=(0, 0, 0, 0), is_main=False, backing_scale=1.0,
    )
    with pytest.raises(ValueError, match="refusing to record"):
        build_screen_record_command(
            Path("recordings/demo/raw.mp4"), duration=5, screen_device=bad_device,
        )


def test_record_screen_fails_if_output_is_missing(tmp_path):
    output = tmp_path / "raw.mp4"

    with patch("screen_harness.recorder.subprocess.run", return_value=CompletedProcess(["ffmpeg"], 0, "ok")):
        result = record_screen(output, duration=1, screen_device=_fake_screen(0))

    assert result.returncode == 1
    assert "did not create a non-empty output file" in result.stdout
