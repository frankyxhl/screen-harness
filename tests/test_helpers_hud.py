"""Unit tests for HUD integration in helpers.start_recording.

These tests use mocks and do not require AppKit or a WindowServer session.
"""

from __future__ import annotations

import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from screen_harness import helpers as _helpers
from screen_harness.helpers import RecordingStartFailed
from screen_harness.screens import PickedScreen, ScreenDevice


_FAKE_SCREEN = ScreenDevice(
    av_index=0,
    av_name="Capture screen 0",
    display_id=12345,
    bounds=(0, 0, 1920, 1080),
    is_main=True,
    backing_scale=2.0,
    appkit_origin=(0.0, 0.0),
    appkit_size=(960.0, 540.0),
)
_FAKE_PICK = PickedScreen(device=_FAKE_SCREEN, reason="default-main")


def _ffmpeg_popen_mock():
    """Return a mock Popen that mimics a running FFmpeg process."""
    proc = MagicMock(spec=subprocess.Popen)
    proc.returncode = 0
    proc.stdin = MagicMock()
    proc.stdout = MagicMock()
    proc.stderr = None  # no stderr pipe → _wait_for_ffmpeg_start skips reader thread
    proc.pid = 99999
    proc.poll.return_value = None  # process still alive; required by HARD FAIL check
    proc.wait.return_value = 0
    return proc


@pytest.fixture()
def isolated_state(tmp_path):
    """Reset helpers._STATE to a fresh RuntimeState rooted at tmp_path.

    Also patches _wait_for_ffmpeg_start to return immediately (popen_time) so
    that tests focused on HUD/region behavior don't wait for the full startup
    timeout. Tests that exercise _wait_for_ffmpeg_start directly live in
    test_helpers_startup_verify.py and do not use this fixture.
    """
    _helpers.configure(tmp_path)
    import time as _time
    with patch("screen_harness.helpers._wait_for_ffmpeg_start", return_value=_time.monotonic()):
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
        # `poll() is None` ⇒ subprocess still alive.  Required by the
        # post-launch survival check (Codex P2 round 2).
        hud_proc.poll.return_value = None

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


    def test_hud_active_false_when_subprocess_dies_during_startup(self, isolated_state):
        """Codex P2 round 2: if the HUD child Popen succeeds but the child
        exits during AppKit import (poll() returns non-None), the helper
        must detect that and write hud_active=False — not lie about a
        process that's already dead."""
        ffmpeg_proc = _ffmpeg_popen_mock()
        dead_hud = MagicMock(spec=subprocess.Popen)
        dead_hud.returncode = 1
        dead_hud.stdin = MagicMock()
        dead_hud.stderr = MagicMock()
        dead_hud.stderr.read.return_value = "ModuleNotFoundError: No module named 'AppKit'"
        dead_hud.pid = 99999
        dead_hud.poll.return_value = 1  # already exited

        def _fake_popen(cmd, **kwargs):
            cmd_str = " ".join(str(c) for c in cmd)
            if "screen_harness.hud" in cmd_str:
                return dead_hud
            return ffmpeg_proc

        with patch("screen_harness.screens.probe_screens", return_value=[_FAKE_SCREEN]), \
             patch("screen_harness.screens.resolve_screen", return_value=_FAKE_PICK), \
             patch("screen_harness.helpers._safe_ffmpeg_version", return_value="n/a"), \
             patch("subprocess.Popen", side_effect=_fake_popen):
            rec_dir = _helpers.start_recording(
                "hud-dies-test",
                region=(100, 100, 800, 600),
                hud=True,
            )

        metadata = json.loads((rec_dir / "metadata.json").read_text())
        assert metadata.get("hud_active") is False


    def test_state_cleared_after_keyboard_interrupt_during_wait(self, isolated_state):
        """Codex P2 round 6: after KeyboardInterrupt during the FFmpeg-start
        wait, _STATE must be cleaned up and the interrupt re-raised so the
        harness does not think a recording is still active."""
        ffmpeg_proc = _ffmpeg_popen_mock()

        def _interrupt(*args, **kwargs):
            raise KeyboardInterrupt("user pressed Ctrl-C during ffmpeg wait")

        with patch("screen_harness.screens.probe_screens", return_value=[_FAKE_SCREEN]), \
             patch("screen_harness.screens.resolve_screen", return_value=_FAKE_PICK), \
             patch("screen_harness.helpers._safe_ffmpeg_version", return_value="n/a"), \
             patch("screen_harness.helpers._wait_for_ffmpeg_start", side_effect=_interrupt), \
             patch("subprocess.Popen", return_value=ffmpeg_proc):
            with pytest.raises(KeyboardInterrupt):
                _helpers.start_recording(
                    "interrupt-test",
                    region=(100, 100, 800, 600),
                    hud=False,
                )

        # After cleanup, _STATE must be reset — the harness must not think
        # a recording is still active.
        assert _helpers._STATE.is_recording is False
        assert _helpers._STATE.process is None


@pytest.fixture()
def isolated_state_real_wait(tmp_path):
    """Like isolated_state but does NOT patch _wait_for_ffmpeg_start.

    Use this for tests that exercise the real startup verification logic
    (e.g. RecordingStartFailed propagation through start_recording).
    """
    _helpers.configure(tmp_path)
    yield tmp_path
    _helpers._STATE.is_recording = False
    _helpers._STATE.process = None
    _helpers._STATE.log_handle = None
    _helpers._STATE.recording_dir = None
    _helpers._STATE.timeline = None
    _helpers._STATE.started_at = None
    _helpers._STATE.screen_inventory = None


class TestTightCropDisablesHUD:
    def test_tight_crop_disables_hud_with_warning(self, isolated_state, capsys):
        """region=(10,10,1900,1060) on 1920×1080 screen — pick_rec_pill_anchor
        returns 'none', so HUD must be suppressed (hud_active=False) and the
        'too close to screen edges' warning must be printed."""
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
            rec_dir = _helpers.start_recording(
                "tight-crop-hud-test",
                region=(10, 10, 1900, 1060),
                hud=True,
            )

        assert not hud_launched, "HUD subprocess should not launch for tight crop"
        metadata = json.loads((rec_dir / "metadata.json").read_text())
        assert metadata.get("hud_active") is False
        captured = capsys.readouterr()
        assert "too close to screen edges" in captured.out


class TestAbortActiveRecordingTearsDownHUD:
    """Finding 2: abort_active_recording must close the HUD stdin and clear hud_process."""

    def test_abort_active_recording_tears_down_hud(self, isolated_state):
        """When a recording with hud=True is aborted, the HUD subprocess stdin
        must be closed and _STATE.hud_process must be reset to None."""
        ffmpeg_proc = _ffmpeg_popen_mock()
        hud_proc = MagicMock(spec=subprocess.Popen)
        hud_proc.returncode = None
        hud_proc.stdin = MagicMock()
        hud_proc.stdin.closed = False
        hud_proc.pid = 77777
        hud_proc.poll.return_value = None  # still alive before abort

        def _fake_popen(cmd, **kwargs):
            cmd_str = " ".join(str(c) for c in cmd)
            if "screen_harness.hud" in cmd_str:
                return hud_proc
            return ffmpeg_proc

        with patch("screen_harness.screens.probe_screens", return_value=[_FAKE_SCREEN]), \
             patch("screen_harness.screens.resolve_screen", return_value=_FAKE_PICK), \
             patch("screen_harness.helpers._safe_ffmpeg_version", return_value="n/a"), \
             patch("subprocess.Popen", side_effect=_fake_popen):
            _helpers.start_recording(
                "abort-hud-test",
                region=(100, 100, 800, 600),
                hud=True,
            )

        assert _helpers._STATE.hud_process is not None

        _helpers.abort_active_recording()

        assert _helpers._STATE.hud_process is None
        hud_proc.stdin.close.assert_called()


class TestHUDCleanedUpWhenMetadataWriteFails:
    """Codex P2 round 10: HUD must be torn down when metadata write fails after HUD launch."""

    def test_hud_cleaned_up_when_metadata_write_fails_after_hud_launch(self, isolated_state):
        """If _write_json raises on the hud_active=True rewrite, start_recording
        must propagate the error and the HUD subprocess must still be torn down."""
        ffmpeg_proc = _ffmpeg_popen_mock()
        hud_proc = MagicMock(spec=subprocess.Popen)
        hud_proc.returncode = None
        hud_proc.stdin = MagicMock()
        hud_proc.stdin.closed = False
        hud_proc.pid = 66666
        hud_proc.poll.return_value = None  # still alive

        def _fake_popen(cmd, **kwargs):
            cmd_str = " ".join(str(c) for c in cmd)
            if "screen_harness.hud" in cmd_str:
                return hud_proc
            return ffmpeg_proc

        # First call (initial metadata write) succeeds; second (hud_active=True) raises.
        with patch("screen_harness.screens.probe_screens", return_value=[_FAKE_SCREEN]), \
             patch("screen_harness.screens.resolve_screen", return_value=_FAKE_PICK), \
             patch("screen_harness.helpers._safe_ffmpeg_version", return_value="n/a"), \
             patch("subprocess.Popen", side_effect=_fake_popen), \
             patch(
                 "screen_harness.helpers._write_json",
                 side_effect=[None, OSError("disk full")],
             ):
            with pytest.raises(OSError, match="disk full"):
                _helpers.start_recording(
                    "hud-metadata-fail",
                    region=(100, 100, 800, 600),
                    hud=True,
                )

        assert hud_proc.stdin.close.called, "HUD stdin must be closed on cleanup"
        assert _helpers._STATE.hud_process is None
        assert _helpers._STATE.is_recording is False


class TestStartRecordingRaisesWhenFFmpegDiesImmediately:
    """Integration: start_recording propagates RecordingStartFailed and resets state."""

    def test_raises_recording_start_failed(self, isolated_state_real_wait):
        """When FFmpeg Popen mock has poll() return 7 immediately,
        start_recording must raise RecordingStartFailed and reset
        _STATE.is_recording to False (cleanup path ran)."""

        proc = MagicMock(spec=subprocess.Popen)
        proc.pid = 55555
        proc.returncode = 7
        proc.poll.return_value = 7
        proc.stdin = MagicMock()
        proc.stdout = MagicMock()
        proc.stderr = None
        proc.wait.return_value = 7

        with patch("screen_harness.screens.probe_screens", return_value=[_FAKE_SCREEN]), \
             patch("screen_harness.screens.resolve_screen", return_value=_FAKE_PICK), \
             patch("screen_harness.helpers._safe_ffmpeg_version", return_value="n/a"), \
             patch("subprocess.Popen", return_value=proc):
            with pytest.raises(RecordingStartFailed) as exc_info:
                _helpers.start_recording(
                    "ffmpeg-dies-test",
                    region=(100, 100, 800, 600),
                    hud=False,
                )

        assert "rc=7" in str(exc_info.value)
        # The exception propagates out of start_recording's BaseException re-raise.
        assert exc_info.type is RecordingStartFailed

    def test_state_cleared_after_recording_start_failed(self, isolated_state_real_wait):
        """Codex P2 round 6: after RecordingStartFailed propagates, _STATE must
        be cleared so the caller is not left thinking a recording is active."""
        proc = MagicMock(spec=subprocess.Popen)
        proc.pid = 55555
        proc.returncode = 1
        proc.poll.return_value = 1
        proc.stdin = MagicMock()
        proc.stdout = MagicMock()
        proc.stderr = None
        proc.wait.return_value = 1

        with patch("screen_harness.screens.probe_screens", return_value=[_FAKE_SCREEN]), \
             patch("screen_harness.screens.resolve_screen", return_value=_FAKE_PICK), \
             patch("screen_harness.helpers._safe_ffmpeg_version", return_value="n/a"), \
             patch("subprocess.Popen", return_value=proc):
            with pytest.raises(RecordingStartFailed):
                _helpers.start_recording(
                    "state-cleared-test",
                    region=(100, 100, 800, 600),
                    hud=False,
                )

        assert _helpers._STATE.is_recording is False
        assert _helpers._STATE.process is None
        assert _helpers._STATE.log_handle is None
        assert _helpers._STATE.recording_dir is None
