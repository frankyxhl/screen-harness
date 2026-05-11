"""Tests for strengthened FFmpeg-startup verification in helpers.py.

Covers:
- Hard WIN: raw_path grows past 1 KB → confirmed
- Hard FAIL: process exits before file appears → RecordingStartFailed
- Timeout fallback: returns popen_time (not now+timeout) with a warning
- Soft WIN: Stream #0 pattern in stderr
- No false-positive match on avfoundation error line
"""

from __future__ import annotations

import io
import time
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch
import subprocess

import pytest

from screen_harness.helpers import RecordingStartFailed, _wait_for_ffmpeg_start


def _make_proc(*, poll_return=None, stderr_bytes: bytes | None = None):
    """Build a minimal mock Popen.

    poll_return=None  → process still alive (default)
    poll_return=<int> → process exited with that code
    stderr_bytes      → bytes returned by an iter-able stderr pipe
    """
    proc = MagicMock(spec=subprocess.Popen)
    proc.pid = 12345
    proc.returncode = poll_return

    if poll_return is None:
        proc.poll.return_value = None
    else:
        proc.poll.return_value = poll_return

    if stderr_bytes is not None:
        # Simulate a binary pipe that yields lines when iterated.
        lines = [l + b"\n" for l in stderr_bytes.split(b"\n") if l]
        proc.stderr = iter(lines)
        # Also support read() for the non-blocking stderr tail in HARD FAIL path.
        proc.stderr = io.BytesIO(stderr_bytes)
    else:
        proc.stderr = None

    return proc


class TestWaitReturnsWhenRawFileGrows:
    """Hard WIN: file exists and exceeds 1024 bytes → returns before timeout."""

    def test_returns_within_timeout(self, tmp_path):
        raw = tmp_path / "raw.mp4"
        proc = _make_proc()

        # Write 2 KB to raw.mp4 before calling _wait_for_ffmpeg_start so the
        # first poll in the loop sees the file already large enough.
        raw.write_bytes(b"X" * 2048)

        start = time.monotonic()
        result = _wait_for_ffmpeg_start(proc, None, raw_path=raw, timeout=5.0)
        elapsed = time.monotonic() - start

        assert isinstance(result, float)
        # Should return well within timeout (file already existed at call time).
        assert elapsed < 2.0


class TestWaitRaisesWhenFFmpegExitsDuringStartup:
    """Hard FAIL: process exits before raw.mp4 grows → RecordingStartFailed."""

    def test_raises_recording_start_failed(self, tmp_path):
        raw = tmp_path / "raw.mp4"
        # File never gets created / stays empty.

        proc = _make_proc(poll_return=1)

        with pytest.raises(RecordingStartFailed) as exc_info:
            _wait_for_ffmpeg_start(proc, None, raw_path=raw, timeout=5.0)

        assert "rc=1" in str(exc_info.value)

    def test_error_message_includes_returncode(self, tmp_path):
        raw = tmp_path / "raw.mp4"
        proc = _make_proc(poll_return=7)

        with pytest.raises(RecordingStartFailed) as exc_info:
            _wait_for_ffmpeg_start(proc, None, raw_path=raw, timeout=5.0)

        assert "rc=7" in str(exc_info.value)


class TestWaitFallbackOnTimeout:
    """Timeout: no file growth, no crash, no stderr pattern → returns popen_time + warning."""

    def test_returns_popen_time_not_now_plus_timeout(self, tmp_path, caplog):
        raw = tmp_path / "raw.mp4"
        # No file, process alive, no stderr.
        proc = _make_proc()

        import logging
        with caplog.at_level(logging.WARNING, logger="screen_harness"):
            before = time.monotonic()
            result = _wait_for_ffmpeg_start(proc, None, raw_path=raw, timeout=0.2)
            after = time.monotonic()

        # Result must be the popen_time captured BEFORE the wait loop, not
        # "now + timeout".  The popen_time is captured at function entry, so it
        # must be ≤ before + a small epsilon.
        assert result <= before + 0.05, (
            f"Expected popen_time (≤{before + 0.05:.3f}) but got {result:.3f}"
        )
        # And it must not be a future time.
        assert result < after

        # A warning must be logged.
        assert any("not confirmed" in r.message or "Popen time" in r.message for r in caplog.records)


class TestWaitSoftMatchStream0:
    """Soft WIN: 'Stream #0' in stderr → function returns."""

    def test_returns_on_stream0_pattern(self, tmp_path):
        raw = tmp_path / "raw.mp4"
        # File never appears, but stderr emits "Stream #0:0"
        proc = _make_proc(stderr_bytes=b"Stream #0:0: Video: h264\n")

        result = _wait_for_ffmpeg_start(proc, None, raw_path=raw, timeout=5.0)
        assert isinstance(result, float)


class TestWaitDoesNotMatchAvfoundationErrorLine:
    """Old b'avfoundation' pattern must NOT trigger on an error line."""

    def test_error_line_does_not_confirm(self, tmp_path, caplog):
        raw = tmp_path / "raw.mp4"
        # Only error-level stderr; no Stream #0, no AVFoundation capture started.
        proc = _make_proc(
            stderr_bytes=b"avfoundation: failed to access screen\n"
        )

        import logging
        with caplog.at_level(logging.WARNING, logger="screen_harness"):
            before = time.monotonic()
            result = _wait_for_ffmpeg_start(proc, None, raw_path=raw, timeout=0.2)

        # Must time out (return popen_time), not confirm on the error line.
        assert result <= before + 0.05, (
            f"Expected timeout fallback (popen_time ≤ {before + 0.05:.3f}) "
            f"but got {result:.3f} — avfoundation error line falsely matched."
        )
        assert any("not confirmed" in r.message or "Popen time" in r.message for r in caplog.records)
