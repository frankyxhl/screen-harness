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
