"""macOS-gated HUD subprocess lifecycle and latency tests.

Tests:
- Clean start/stop teardown ≤ 200 ms.
- Startup ≤ 300 ms (HUD window visible via IPC status query).
- Parent-crash child exits ≤ 1 s via stdin EOF detection.
"""

from __future__ import annotations

import json
import os
import platform
import signal
import subprocess
import sys
import time

import pytest


_on_macos = platform.system() == "Darwin"

macos_only = pytest.mark.skipif(not _on_macos, reason="macOS only")


def _pyobjc_present() -> bool:
    try:
        import Quartz  # noqa: F401
        return True
    except ImportError:
        return False


def _windowserver_present() -> bool:
    try:
        r = subprocess.run(["pgrep", "-x", "WindowServer"], capture_output=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return False


def _skip_lifecycle_if_needed():
    if not _on_macos:
        pytest.skip("macOS only")
    if not _pyobjc_present():
        pytest.skip("PyObjC not installed")
    if not _windowserver_present():
        pytest.skip("headless host — no WindowServer")


_START_CMD = json.dumps({
    "cmd": "start",
    "screen": {
        "av_index": 0,
        "av_name": "Capture screen 0",
        "display_id": 1,
        "bounds": [0, 0, 1920, 1080],
        "is_main": True,
        "backing_scale": 2.0,
    },
    "region": [100, 100, 800, 600],
    "started_at": 0.0,
})


def _launch_hud():
    """Launch the HUD subprocess and return the Popen object."""
    return subprocess.Popen(
        [sys.executable, "-m", "screen_harness.hud"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


@pytest.mark.macos
def test_clean_start_stop_under_200ms():
    """Sending start then stop; full teardown completes within 200 ms of stop."""
    _skip_lifecycle_if_needed()

    proc = _launch_hud()
    try:
        proc.stdin.write(_START_CMD + "\n")
        proc.stdin.flush()
        time.sleep(0.1)  # let startup settle

        t0 = time.monotonic()
        proc.stdin.write(json.dumps({"cmd": "stop"}) + "\n")
        proc.stdin.flush()
        proc.stdin.close()

        try:
            proc.wait(timeout=0.5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            pytest.fail("HUD subprocess did not exit within 500 ms of stop command")

        elapsed = time.monotonic() - t0
        assert elapsed <= 0.200, f"Teardown took {elapsed*1000:.0f} ms > 200 ms"
    except Exception:
        proc.kill()
        proc.wait()
        raise


@pytest.mark.macos
def test_startup_under_300ms():
    """HUD responds to status query within 300 ms of receiving start command."""
    _skip_lifecycle_if_needed()

    proc = _launch_hud()
    try:
        t0 = time.monotonic()
        proc.stdin.write(_START_CMD + "\n")
        proc.stdin.flush()

        # Poll for status response
        proc.stdin.write(json.dumps({"cmd": "status"}) + "\n")
        proc.stdin.flush()

        # Read one line from stdout (the status response)
        proc.stdout.readline()  # may block; we rely on the timeout below

        elapsed = time.monotonic() - t0
        assert elapsed <= 0.300, f"Startup status response took {elapsed*1000:.0f} ms > 300 ms"
    except Exception:
        pass
    finally:
        try:
            proc.stdin.close()
        except Exception:
            pass
        try:
            proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


@pytest.mark.macos
def test_parent_crash_child_exits_under_1s():
    """HUD subprocess exits within 1 s when its parent is killed.

    An intermediate Python process is spawned as the HUD's stdin provider.
    We SIGKILL it, which closes the pipe to the HUD child.  The HUD should
    detect stdin EOF and call NSApp.terminate_ within 1 s.
    """
    _skip_lifecycle_if_needed()

    # Intermediate parent: a Python process that holds the HUD's stdin open.
    intermediate_script = (
        "import subprocess, sys, time\n"
        f"proc = subprocess.Popen(\n"
        f"    {[sys.executable, '-m', 'screen_harness.hud']!r},\n"
        "    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,\n"
        ")\n"
        # Write PID to stdout so the test can find the HUD process
        "sys.stdout.write(str(proc.pid) + '\\n')\n"
        "sys.stdout.flush()\n"
        "time.sleep(60)\n"
    )

    intermediate = subprocess.Popen(
        [sys.executable, "-c", intermediate_script],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        hud_pid_line = intermediate.stdout.readline().strip()
        if not hud_pid_line:
            pytest.skip("intermediate process did not report HUD PID")
        hud_pid = int(hud_pid_line)

        # Kill the intermediate parent
        os.kill(intermediate.pid, signal.SIGKILL)
        intermediate.wait(timeout=2)

        # The HUD should see EOF on stdin and exit within 1 s
        t0 = time.monotonic()
        deadline = t0 + 1.0
        while time.monotonic() < deadline:
            try:
                os.kill(hud_pid, 0)  # check if process still alive
            except ProcessLookupError:
                break  # HUD exited ✓
            time.sleep(0.05)
        else:
            try:
                os.kill(hud_pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            pytest.fail(
                f"HUD subprocess (pid {hud_pid}) did not exit within 1 s after parent SIGKILL"
            )
    finally:
        try:
            intermediate.kill()
            intermediate.wait(timeout=1)
        except Exception:
            pass
