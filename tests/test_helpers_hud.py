"""Unit tests for HUD integration in helpers.start_recording.

These tests use mocks and do not require AppKit or a WindowServer session.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from screen_harness import helpers as _helpers
from screen_harness.screens import PickedScreen, ScreenDevice


_FAKE_SCREEN = ScreenDevice(
    av_index=0,
    av_name="Capture screen 0",
    display_id=12345,
    bounds=(0, 0, 1920, 1080),
    is_main=True,
    backing_scale=2.0,
)
_FAKE_PICK = PickedScreen(device=_FAKE_SCREEN, reason="default-main")


def _ffmpeg_popen_mock():
    """Return a mock Popen that mimics a running FFmpeg process."""
    proc = MagicMock(spec=subprocess.Popen)
    proc.returncode = 0
    proc.stdin = MagicMock()
    proc.stdout = MagicMock()
    proc.stderr = None  # no stderr pipe → _wait_for_ffmpeg_start returns immediately
    proc.pid = 99999
    proc.wait.return_value = 0
    return proc


@pytest.fixture()
def isolated_state(tmp_path):
    """Reset helpers._STATE to a fresh RuntimeState rooted at tmp_path."""
    _helpers.configure(tmp_path)
    yield tmp_path
    # Ensure we don't leave a stale recording state for other tests
    _helpers._STATE.is_recording = False
    _helpers._STATE.process = None
    _helpers._STATE.log_handle = None
    _helpers._STATE.recording_dir = None
    _helpers._STATE.timeline = None
    _helpers._STATE.started_at = None
    _helpers._STATE.screen_inventory = None


class TestRecordingProceedsWhenHUDLaunchFails:
    """CHG-2218 §Plan #9 — HUD-failure-recovery test."""

    def test_recording_proceeds_when_hud_launch_fails(self, isolated_state):
        """start_recording completes and metadata has hud_active=False when
        the HUD subprocess cannot be launched (Popen raises OSError)."""
        tmp_path = isolated_state

        ffmpeg_proc = _ffmpeg_popen_mock()

        def _fake_popen(cmd, **kwargs):
            # Allow FFmpeg Popen; raise on HUD Popen (hud module path)
            cmd_str = " ".join(str(c) for c in cmd)
            if "screen_harness.hud" in cmd_str:
                raise OSError("simulated HUD launch failure")
            return ffmpeg_proc

        with patch("screen_harness.screens.probe_screens", return_value=[_FAKE_SCREEN]), \
             patch("screen_harness.screens.resolve_screen", return_value=_FAKE_PICK), \
             patch("screen_harness.helpers._safe_ffmpeg_version", return_value="n/a"), \
             patch("subprocess.Popen", side_effect=_fake_popen):
            rec_dir = _helpers.start_recording(
                "hud-failure-test",
                region=(100, 100, 800, 600),
                hud=True,
            )

        assert rec_dir is not None
        metadata_path = rec_dir / "metadata.json"
        assert metadata_path.exists()
        metadata = json.loads(metadata_path.read_text())
        assert metadata.get("hud_active") is False

    def test_hud_active_true_when_hud_starts_successfully(self, isolated_state):
        """metadata.json has hud_active=True when HUD subprocess starts."""
        ffmpeg_proc = _ffmpeg_popen_mock()
        hud_proc = MagicMock(spec=subprocess.Popen)
        hud_proc.returncode = None
        hud_proc.stdin = MagicMock()
        hud_proc.pid = 88888

        def _fake_popen(cmd, **kwargs):
            cmd_str = " ".join(str(c) for c in cmd)
            if "screen_harness.hud" in cmd_str:
                return hud_proc
            return ffmpeg_proc

        with patch("screen_harness.screens.probe_screens", return_value=[_FAKE_SCREEN]), \
             patch("screen_harness.screens.resolve_screen", return_value=_FAKE_PICK), \
             patch("screen_harness.helpers._safe_ffmpeg_version", return_value="n/a"), \
             patch("subprocess.Popen", side_effect=_fake_popen):
            rec_dir = _helpers.start_recording(
                "hud-success-test",
                region=(100, 100, 800, 600),
                hud=True,
            )

        metadata = json.loads((rec_dir / "metadata.json").read_text())
        assert metadata.get("hud_active") is True

    def test_hud_skipped_without_region(self, isolated_state):
        """HUD is skipped (not launched) when no region is provided."""
        ffmpeg_proc = _ffmpeg_popen_mock()
        hud_launched = []

        def _fake_popen(cmd, **kwargs):
            cmd_str = " ".join(str(c) for c in cmd)
            if "screen_harness.hud" in cmd_str:
                hud_launched.append(True)
            return ffmpeg_proc

        with patch("screen_harness.screens.probe_screens", return_value=[_FAKE_SCREEN]), \
             patch("screen_harness.screens.resolve_screen", return_value=_FAKE_PICK), \
             patch("screen_harness.helpers._safe_ffmpeg_version", return_value="n/a"), \
             patch("subprocess.Popen", side_effect=_fake_popen):
            _helpers.start_recording("no-hud-no-region", hud=True)

        assert not hud_launched, "HUD should not launch when no region is specified"

    def test_hud_false_kwarg_skips_hud(self, isolated_state):
        """start_recording(..., hud=False) never launches HUD subprocess."""
        ffmpeg_proc = _ffmpeg_popen_mock()
        hud_launched = []

        def _fake_popen(cmd, **kwargs):
            cmd_str = " ".join(str(c) for c in cmd)
            if "screen_harness.hud" in cmd_str:
                hud_launched.append(True)
            return ffmpeg_proc

        with patch("screen_harness.screens.probe_screens", return_value=[_FAKE_SCREEN]), \
             patch("screen_harness.screens.resolve_screen", return_value=_FAKE_PICK), \
             patch("screen_harness.helpers._safe_ffmpeg_version", return_value="n/a"), \
             patch("subprocess.Popen", side_effect=_fake_popen):
            _helpers.start_recording(
                "hud-disabled",
                region=(100, 100, 800, 600),
                hud=False,
            )

        assert not hud_launched


class TestRegionOutOfBoundsInHelpers:
    """RegionOutOfBoundsError raised by start_recording for overflow regions."""

    def test_overflow_region_raises(self, isolated_state):
        from screen_harness.hud import RegionOutOfBoundsError

        with patch("screen_harness.screens.probe_screens", return_value=[_FAKE_SCREEN]), \
             patch("screen_harness.screens.resolve_screen", return_value=_FAKE_PICK), \
             patch("screen_harness.helpers._safe_ffmpeg_version", return_value="n/a"):
            with pytest.raises(RegionOutOfBoundsError):
                _helpers.start_recording(
                    "overflow",
                    region=(200, 0, 1800, 100),  # 200+1800=2000 > 1920
                    hud=True,
                )

    def test_valid_region_does_not_raise(self, isolated_state):
        ffmpeg_proc = _ffmpeg_popen_mock()
        with patch("screen_harness.screens.probe_screens", return_value=[_FAKE_SCREEN]), \
             patch("screen_harness.screens.resolve_screen", return_value=_FAKE_PICK), \
             patch("screen_harness.helpers._safe_ffmpeg_version", return_value="n/a"), \
             patch("subprocess.Popen", return_value=ffmpeg_proc):
            rec_dir = _helpers.start_recording(
                "valid-region",
                region=(100, 100, 800, 600),
                hud=False,
            )
        assert rec_dir is not None
