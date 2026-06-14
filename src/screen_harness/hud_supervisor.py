"""Parent-side HUD subprocess management.

Launches ``python -m screen_harness.hud``, sends it the start command, and
tears it down on stop/abort/atexit. The HUD is strictly best-effort: a
recording must never fail because the HUD could not start.
"""

from __future__ import annotations

import atexit
import json
import logging
import subprocess
import time
from typing import TYPE_CHECKING

from . import runtime

if TYPE_CHECKING:
    from .screens import ScreenDevice

logger = logging.getLogger("screen_harness")

_HUD_ATEXIT_REGISTERED = False


def _launch_hud_subprocess(
    *,
    screen_device: "ScreenDevice",
    region: tuple[int, int, int, int],
    started_at: float,
) -> "subprocess.Popen | None":
    """Launch ``python -m screen_harness.hud`` and send the start command.

    Returns the Popen object on success, or None if the subprocess cannot
    be started (recording must not fail because the HUD failed).
    """
    import sys as _sys
    from dataclasses import asdict as _asdict

    try:
        hud_proc = subprocess.Popen(
            [_sys.executable, "-m", "screen_harness.hud"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except OSError as exc:
        logger.warning("HUD subprocess could not be launched (%s); recording continues without HUD.", exc)
        return None

    try:
        screen_dict = _asdict(screen_device)
        # bounds is a tuple — JSON needs a list
        screen_dict["bounds"] = list(screen_dict["bounds"])
        start_cmd = json.dumps({
            "cmd": "start",
            "screen": screen_dict,
            "region": list(region),
            "started_at": started_at,
        }) + "\n"
        if hud_proc.stdin is None:
            raise OSError("HUD subprocess has no stdin pipe")
        hud_proc.stdin.write(start_cmd)
        hud_proc.stdin.flush()
    except (OSError, BrokenPipeError) as exc:
        logger.warning("HUD start command failed (%s); recording continues without HUD.", exc)
        try:
            hud_proc.kill()
            hud_proc.wait(timeout=1)
        except Exception:
            pass
        return None

    # Codex P2 round 2 (PR #7): the child may have exited during AppKit
    # import (e.g. missing/broken PyObjC) even though stdin.write succeeded
    # because the pipe buffer absorbs the write before the kernel notices
    # the dead reader.  Give the child a short window to crash, then
    # poll() and treat early-exit as a launch failure so `hud_active` in
    # metadata.json reflects reality.
    time.sleep(0.15)
    if hud_proc.poll() is not None:
        rc = hud_proc.returncode
        try:
            stderr_tail = (hud_proc.stderr.read() or "").strip()[-300:] if hud_proc.stderr else ""
        except Exception:
            stderr_tail = ""
        logger.warning(
            "HUD subprocess exited during startup (rc=%s); recording continues without HUD. stderr: %s",
            rc, stderr_tail,
        )
        return None

    return hud_proc


def _stop_hud_subprocess(hud_proc: "subprocess.Popen | None") -> None:
    """Close HUD subprocess stdin → child sees EOF → terminates within 200 ms."""
    if hud_proc is None:
        return
    try:
        if hud_proc.stdin and not hud_proc.stdin.closed:
            hud_proc.stdin.close()
    except (OSError, BrokenPipeError):
        pass
    try:
        hud_proc.wait(timeout=0.5)
    except subprocess.TimeoutExpired:
        try:
            hud_proc.kill()
            hud_proc.wait(timeout=0.5)
        except Exception:
            pass
    except Exception:
        pass


def _atexit_hud_cleanup() -> None:
    """atexit handler — tears down HUD if the process exits without stop_recording()."""
    _stop_hud_subprocess(runtime._STATE.hud_process)
    runtime._STATE.hud_process = None


def ensure_atexit_registered() -> None:
    """Register HUD teardown once per process (idempotent guard)."""
    global _HUD_ATEXIT_REGISTERED
    if not _HUD_ATEXIT_REGISTERED:
        atexit.register(_atexit_hud_cleanup)
        _HUD_ATEXIT_REGISTERED = True
