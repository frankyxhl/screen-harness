from subprocess import CompletedProcess
from unittest.mock import patch

from screen_harness import admin


def test_parse_avfoundation_devices_extracts_video_and_audio():
    text = """
[AVFoundation indev @ 0x123] AVFoundation video devices:
[AVFoundation indev @ 0x123] [0] Capture screen 0
[AVFoundation indev @ 0x123] [1] FaceTime HD Camera
[AVFoundation indev @ 0x123] AVFoundation audio devices:
[AVFoundation indev @ 0x123] [0] MacBook Pro Microphone
"""

    devices = admin.parse_avfoundation_devices(text)

    assert devices.video == [{"index": "0", "name": "Capture screen 0"}, {"index": "1", "name": "FaceTime HD Camera"}]
    assert devices.audio == [{"index": "0", "name": "MacBook Pro Microphone"}]


def test_parse_avfoundation_devices_handles_missing_audio():
    text = """
[AVFoundation indev @ 0x123] AVFoundation video devices:
[AVFoundation indev @ 0x123] [0] Capture screen 0
[AVFoundation indev @ 0x123] AVFoundation audio devices:
[in#0 @ 0x456] Error opening input: Input/output error
"""

    devices = admin.parse_avfoundation_devices(text)

    assert devices.video == [{"index": "0", "name": "Capture screen 0"}]
    assert devices.audio == []


def test_doctor_summary_reports_screen_and_missing_audio():
    devices = admin.AVFoundationDevices(video=[{"index": "0", "name": "Capture screen 0"}], audio=[])

    summary = admin.build_doctor_summary(
        ffmpeg_path="/opt/homebrew/bin/ffmpeg",
        ffmpeg_version="ffmpeg version 8.0.1",
        devices=devices,
        device_error="Input/output error",
    )

    assert "ffmpeg: ok" in summary
    assert "screen capture: ok" in summary
    assert "microphone: not detected" in summary
    assert "Input/output error" in summary


def test_parse_ffmpeg_filters_extracts_filter_names():
    text = """
Filters:
  T. drawbox           V->V       Draw a colored box on the input video.
  .. subtitles         V->V       Render text subtitles onto input video.
"""

    assert admin.parse_ffmpeg_filters(text) == {"drawbox", "subtitles"}


def test_doctor_reports_missing_ffmpeg(monkeypatch):
    monkeypatch.setattr(admin.shutil, "which", lambda _: None)
    monkeypatch.setattr(admin, "bundled_full_ffmpeg", lambda: None)

    summary = admin.doctor()

    assert "ffmpeg: missing" in summary
    assert "screen capture: not detected" in summary
    assert "render ffmpeg: missing" in summary


def test_ffmpeg_version_returns_first_line():
    completed = CompletedProcess(["ffmpeg"], 0, "ffmpeg version 8.0.1\nbuilt with…\n")
    with patch("screen_harness.admin.subprocess.run", return_value=completed):
        assert admin.ffmpeg_version("ffmpeg").startswith("ffmpeg version 8.0.1")


def test_ffmpeg_filters_returns_parsed_set():
    completed = CompletedProcess(
        ["ffmpeg"],
        0,
        "Filters:\n  T. drawbox           V->V       Draw a box.\n  .. subtitles         V->V       Render subs.\n",
    )
    with patch("screen_harness.admin.subprocess.run", return_value=completed):
        assert admin.ffmpeg_filters("ffmpeg") == {"drawbox", "subtitles"}


def test_list_avfoundation_devices_surfaces_error_line():
    completed = CompletedProcess(
        ["ffmpeg"],
        1,
        "[AVFoundation indev @ 0x1] AVFoundation video devices:\n"
        "[AVFoundation indev @ 0x1] [0] Capture screen 0\n"
        "Error opening input: Input/output error\n",
    )
    with patch("screen_harness.admin.subprocess.run", return_value=completed):
        devices, error = admin.list_avfoundation_devices("ffmpeg")
    assert devices.video == [{"index": "0", "name": "Capture screen 0"}]
    assert error == "Error opening input: Input/output error"


def test_ffprobe_binary_uses_explicit_env(monkeypatch, tmp_path):
    fake = tmp_path / "ffprobe"
    fake.write_text("")
    monkeypatch.setenv("SCREEN_HARNESS_FFPROBE", str(fake))
    assert admin.ffprobe_binary() == str(fake)


def test_ffprobe_binary_falls_back_to_ffmpeg_sibling(monkeypatch, tmp_path):
    monkeypatch.delenv("SCREEN_HARNESS_FFPROBE", raising=False)
    sibling = tmp_path / "ffprobe"
    sibling.write_text("")
    monkeypatch.setenv("SCREEN_HARNESS_FFMPEG", str(tmp_path / "ffmpeg"))
    assert admin.ffprobe_binary() == str(sibling)


def test_doctor_reports_render_filters_when_available(monkeypatch):
    monkeypatch.setattr(admin.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(admin, "bundled_full_ffmpeg", lambda: "/opt/full/bin/ffmpeg")
    monkeypatch.setattr(admin, "ffmpeg_version", lambda path: "ffmpeg version 8.0.1")
    monkeypatch.setattr(
        admin,
        "list_avfoundation_devices",
        lambda path: (
            admin.AVFoundationDevices(
                video=[{"index": "0", "name": "Capture screen 0"}],
                audio=[],
            ),
            None,
        ),
    )
    monkeypatch.setattr(admin, "ffmpeg_filters", lambda path: {"subtitles", "drawbox"})

    summary = admin.doctor()

    assert "ffmpeg: ok" in summary
    assert "screen capture: ok" in summary
    assert "render ffmpeg: ok" in summary


def test_run_doctor_prints_summary_and_returns_zero(monkeypatch, capsys):
    monkeypatch.setattr(admin, "doctor", lambda: "stub-summary")
    rc = admin.run_doctor()
    assert rc == 0
    assert "stub-summary" in capsys.readouterr().out
