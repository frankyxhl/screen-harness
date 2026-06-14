"""Recording lifecycle: start, confirm, stop, abort.

Owns the FFmpeg capture process (as a process group), the startup
confirmation wait, and the metadata bookkeeping around a recording session.
State lives in :mod:`screen_harness.runtime`; the HUD subprocess is managed
by :mod:`screen_harness.hud_supervisor`.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import signal
import subprocess
import time
from pathlib import Path
from typing import IO

from . import hud_supervisor, probing, runtime
from .project import init_project
from .recorder import build_screen_record_command
from .templates import get_template
from .timeline import Timeline, local_now

logger = logging.getLogger("screen_harness")


class RecordingStartFailed(RuntimeError):
    """Raised when FFmpeg exits with a non-zero code before recording is confirmed."""


def start_recording(
    name: str,
    *,
    screen: str | None = None,
    app: str | None = None,
    mic: str | None = None,
    intro: str | dict | None = None,
    template: str | None = None,
    capture_cursor: bool = True,
    capture_mouse_clicks: bool = True,
    region: tuple[int, int, int, int] | None = None,
    hud: bool = True,
) -> Path:
    _STATE = runtime._STATE
    init_project(_STATE.root)
    template_name = get_template(template).name
    recording_id = Timeline.recording_id(name)
    recording_dir = _STATE.root / "recordings" / recording_id
    recording_dir.mkdir(parents=True, exist_ok=True)
    raw = recording_dir / "raw.mp4"
    timeline = Timeline.create(
        path=recording_dir / "timeline.json",
        recording_id=recording_id,
        title=name,
        source_video="raw.mp4",
        intro=_intro_payload(intro),
    )
    ffmpeg_path = shutil.which("ffmpeg") or "ffmpeg"

    # Resolve the recording screen via smart selection.
    from .screens import probe_screens, resolve_screen
    from dataclasses import asdict as _asdict

    if _STATE.screen_inventory is None:
        # No try/except — probe failures must propagate. Silently falling back
        # to AVFoundation index 0 is the camera-misuse bug D1 exists to
        # prevent (Codex bot finding P1 on PR #5, round 2).
        _STATE.screen_inventory = probe_screens(ffmpeg=ffmpeg_path)
        print("Available screens:")
        for s in _STATE.screen_inventory:
            main_marker = "  MAIN" if s.is_main else ""
            print(f"  [{s.av_index}] {s.av_name}  display_id={s.display_id} bounds={s.bounds}{main_marker}")

    _screen_spec: str | int | None = screen
    if _screen_spec is not None:
        try:
            _screen_spec = int(_screen_spec)
        except (ValueError, TypeError):
            pass
    # Likewise: resolve_screen failures (e.g. user passed a camera index, or
    # auto:<App> with no front window AND no main display) must raise.
    picked = resolve_screen(_screen_spec, app=app, ffmpeg=ffmpeg_path)
    print(f"Recording from: [{picked.device.av_index}] {picked.device.av_name}  ({picked.reason})")
    picked_screen_meta = _asdict(picked.device) | {"reason": picked.reason}
    screen_device_arg = picked.device

    # Validate region bounds before doing anything else.
    if region is not None:
        from .hud import validate_region_for_screen
        validate_region_for_screen(region, picked.device)

    # Determine if the HUD can and should be shown.
    # The HUD requires a pill anchor that fits entirely outside the crop rect.
    # Use pick_rec_pill_anchor to check: if it returns "none", no placement fits.
    hud_eligible = False
    if hud and region is not None:
        from .hud import pick_rec_pill_anchor, transform_region_to_appkit
        _crop_appkit = transform_region_to_appkit(region, picked.device)
        _screen_appkit = (*picked.device.appkit_origin, *picked.device.appkit_size)
        _pill_anchor = pick_rec_pill_anchor(_crop_appkit, _screen_appkit)
        if _pill_anchor == "none":
            print(
                "HUD disabled — crop region is too close to screen edges for the REC pill to fit outside.",
                flush=True,
            )
        else:
            hud_eligible = True
    elif hud and region is None:
        print(
            "Full-screen recording — HUD disabled; pass region= to enable",
            flush=True,
        )

    metadata = {
        "recording_id": recording_id,
        "name": name,
        "created_at": timeline.data["created_at"],
        "recording_started_at": timeline.data["created_at"],
        "recording_stopped_at": None,
        "duration": None,
        "status": "recording",
        "raw_video": "raw.mp4",
        "ffmpeg_path": ffmpeg_path,
        "ffmpeg_version": probing._safe_ffmpeg_version(ffmpeg_path),
        "canvas": None,
        "render_template": template_name,
        "capture_cursor": capture_cursor,
        "capture_mouse_clicks": capture_mouse_clicks,
        "region": list(region) if region else None,
        "picked_screen": picked_screen_meta,
        "hud_active": False,  # updated below if HUD starts
        "error": None,
    }
    runtime._write_json(recording_dir / "metadata.json", metadata)
    log_handle = (recording_dir / "ffmpeg.log").open("w")
    cmd = build_screen_record_command(
        raw,
        duration=None,
        screen_device=screen_device_arg,
        audio_index=mic,
        capture_cursor=capture_cursor,
        capture_mouse_clicks=capture_mouse_clicks,
        region=region,
    )
    # FFmpeg stderr is captured separately so we can watch for the
    # "AVFoundation capture started" line to get an accurate started_at.
    ffmpeg_stderr_pipe = subprocess.PIPE

    # `start_new_session=True` puts FFmpeg (and any AVFoundation helper
    # subprocesses it forks) into a fresh process group so we can SIGTERM the
    # whole tree on stop/abort instead of leaving zombies.
    process = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=log_handle,
        stderr=ffmpeg_stderr_pipe,
        start_new_session=True,
    )

    # Populate runtime state IMMEDIATELY after Popen so any KeyboardInterrupt
    # or BaseException during the ~5 s FFmpeg-start wait or HUD launch can be
    # cleaned up by `abort_active_recording()`.  Previously these fields were
    # only set *after* both waits completed, so an interrupt during the wait
    # window orphaned FFmpeg recording in the background (Codex P2 round 4).
    _STATE.recording_dir = recording_dir
    _STATE.timeline = timeline
    _STATE.process = process
    _STATE.log_handle = log_handle
    _STATE.is_recording = True
    _STATE.hud_process = None
    _STATE.started_at = None

    try:
        # Wait for FFmpeg to confirm capture has started (up to 5 s).
        started_at = _wait_for_ffmpeg_start(process, log_handle, raw_path=raw, timeout=5.0)
        _STATE.started_at = started_at

        # Launch HUD subprocess (best-effort; recording must not fail if HUD fails).
        hud_proc: subprocess.Popen | None = None
        if hud_eligible:
            assert region is not None  # hud_eligible is only set when region is not None
            hud_proc = hud_supervisor._launch_hud_subprocess(
                screen_device=picked.device,
                region=region,
                started_at=started_at,
            )
            if hud_proc is not None:
                _STATE.hud_process = hud_proc
                metadata["hud_active"] = True
                runtime._write_json(recording_dir / "metadata.json", metadata)
    except BaseException:
        _cleanup_failed_start(process, log_handle, hud_proc=_STATE.hud_process)
        raise

    hud_supervisor.ensure_atexit_registered()

    return recording_dir


def _signal_process_group(process: subprocess.Popen, sig: int) -> None:
    """Send `sig` to the process's whole group; fall back to the leader on macOS edge cases."""
    try:
        os.killpg(os.getpgid(process.pid), sig)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            process.send_signal(sig)
        except (ProcessLookupError, OSError):
            pass


def _cleanup_failed_start(
    process: subprocess.Popen,
    log_handle: "IO[str] | None",
    *,
    hud_proc: "subprocess.Popen | None" = None,
) -> None:
    """Best-effort teardown after start_recording fails mid-startup.

    Kills the FFmpeg process group, closes the log handle, terminates any
    partial HUD subprocess, and resets _STATE to a clean (not-recording)
    state.  All sub-operations are wrapped individually so a failure in one
    step does not prevent the others from running.
    """
    try:
        _signal_process_group(process, signal.SIGTERM)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _signal_process_group(process, signal.SIGKILL)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
    except Exception:
        pass
    try:
        if log_handle is not None:
            log_handle.close()
    except Exception:
        pass
    hud_supervisor._stop_hud_subprocess(hud_proc)
    _STATE = runtime._STATE
    _STATE.is_recording = False
    _STATE.process = None
    _STATE.log_handle = None
    _STATE.recording_dir = None
    _STATE.timeline = None
    _STATE.started_at = None
    _STATE.hud_process = None


# FFmpeg stderr lines that confirm avfoundation capture has begun.
# Intentionally narrow: b"avfoundation" (lower-case) was removed because it
# also matches FFmpeg error lines like "avfoundation: failed to access screen",
# producing false positives. b"frame=" / b"fps=" were removed because they
# appear only after encoding starts (too late) and can appear in error context
# too. b"Stream #0" is added because FFmpeg prints it when the output stream is
# opened, which reliably indicates capture has begun.
_FFMPEG_STARTED_PATTERNS = (
    b"AVFoundation capture started",
    b"Stream #0",
)


def _wait_for_ffmpeg_start(
    process: subprocess.Popen,
    log_handle: "IO[str]",
    *,
    raw_path: Path,
    timeout: float = 5.0,
) -> float:
    """Poll until recording is confirmed, FFmpeg crashes, or timeout expires.

    Verification priority:
    1. HARD WIN  — raw_path exists and its size exceeds 1024 bytes.  The file
       is actively being written; capture is confirmed.  Returns monotonic time.
    2. HARD FAIL — process.poll() is not None before the file grows.  FFmpeg
       died during startup.  Raises RecordingStartFailed with the return code
       and the last ~300 chars of stderr if available.
    3. SOFT WIN  — a stderr pattern from _FFMPEG_STARTED_PATTERNS matched.
       Returns confirmed_at[0] only when no hard-fail has occurred.
    4. TIMEOUT   — deadline passed with no signal.  Logs a warning and returns
       popen_time (the time captured before the loop — not now+timeout) so that
       duration metadata stays anchored to the actual Popen call.

    Stderr bytes are forwarded to *log_handle* so ffmpeg.log remains complete.
    """
    import threading

    # Capture popen_time BEFORE the wait loop so the timeout fallback returns
    # the actual launch time, not now+timeout (PR #7 Codex P2 round 2).
    popen_time = time.monotonic()
    deadline = popen_time + timeout
    confirmed_at: list[float] = []

    stderr_pipe = getattr(process, "stderr", None)

    if stderr_pipe is not None:
        # Read FFmpeg stderr in a background thread so we don't block the poll
        # loop waiting for lines that may never arrive.
        def _reader():
            try:
                for raw_line in stderr_pipe:
                    if log_handle:
                        try:
                            log_handle.write(raw_line.decode("utf-8", errors="replace"))
                            log_handle.flush()
                        except (OSError, ValueError):
                            pass
                    if not confirmed_at:
                        for pat in _FFMPEG_STARTED_PATTERNS:
                            if pat in raw_line:
                                confirmed_at.append(time.monotonic())
                                break
            except Exception:
                pass

        t = threading.Thread(target=_reader, daemon=True)
        t.start()

    # Main poll loop — 50 ms cadence.
    while time.monotonic() < deadline:
        # HARD WIN: output file is growing.
        if raw_path.exists() and raw_path.stat().st_size > 1024:
            return time.monotonic()

        # HARD FAIL: process exited before any bytes were written.
        _poll = getattr(process, "poll", None)
        if _poll is not None and _poll() is not None:
            stderr_tail = ""
            if stderr_pipe is not None:
                try:
                    chunk = stderr_pipe.read(300)
                    if chunk:
                        stderr_tail = f" stderr: {chunk.decode('utf-8', errors='replace')[-300:]}"
                except Exception:
                    pass
            raise RecordingStartFailed(
                f"FFmpeg exited rc={process.returncode} during startup{stderr_tail}"
            )

        # SOFT WIN: stderr pattern matched (fallback; less reliable than file growth).
        if confirmed_at:
            return confirmed_at[0]

        time.sleep(0.05)

    # TIMEOUT: no signal received within the deadline.
    if not confirmed_at:
        logger.warning(
            "FFmpeg capture start not confirmed within %.1fs; "
            "using Popen time as started_at",
            timeout,
        )
        return popen_time

    return confirmed_at[0]


def stop_recording() -> Path:
    _STATE = runtime._STATE
    if not _STATE.is_recording or not _STATE.process or not _STATE.recording_dir:
        raise RuntimeError("no active recording")
    process = _STATE.process
    recording_dir = _STATE.recording_dir
    log_handle = _STATE.log_handle
    hud_proc = _STATE.hud_process
    try:
        # Tear down HUD first (closes stdin → child sees EOF → exits within 200 ms).
        hud_supervisor._stop_hud_subprocess(hud_proc)

        # Politely ask FFmpeg to stop. Any I/O error here just falls through
        # to the wait/terminate/kill cascade below — we never want a stdin
        # hiccup to leave the process or log handle leaked.
        if process.stdin:
            try:
                process.stdin.write(b"q")
                process.stdin.flush()
            except (BrokenPipeError, OSError, ValueError):
                pass
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            _signal_process_group(process, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                _signal_process_group(process, signal.SIGKILL)
                process.wait(timeout=5)
        duration = runtime._elapsed()
        metadata_path = recording_dir / "metadata.json"
        metadata = json.loads(metadata_path.read_text())
        metadata["recording_stopped_at"] = local_now().isoformat()
        metadata["duration"] = round(duration, 3)
        metadata["status"] = "stopped" if process.returncode == 0 else "error"
        metadata["error"] = None if process.returncode == 0 else f"ffmpeg exited {process.returncode}"
        metadata["canvas"] = probing._probe_canvas(recording_dir / "raw.mp4")
        runtime._write_json(metadata_path, metadata)
        return recording_dir
    finally:
        # Always release the log handle and recording flag, even when the
        # metadata write or wait cascade raises — otherwise a single failed
        # stop leaves the runtime stuck claiming a recording is live.
        if log_handle is not None:
            try:
                log_handle.close()
            except OSError:
                pass
        _STATE.is_recording = False
        _STATE.process = None
        _STATE.log_handle = None
        _STATE.hud_process = None


def abort_active_recording() -> None:
    _STATE = runtime._STATE
    if not _STATE.is_recording or not _STATE.process:
        return
    process = _STATE.process
    log_handle = _STATE.log_handle
    recording_dir = _STATE.recording_dir
    hud_proc = _STATE.hud_process
    try:
        # Tear down HUD first so the pill disappears immediately.
        hud_supervisor._stop_hud_subprocess(hud_proc)

        # The outer finally below always nulls runtime state, so a metadata
        # write or log close that raises here cannot leave the harness wedged
        # into thinking a recording is still live — same anti-wedge guarantee
        # `stop_recording` provides. The inner try below only handles the
        # SIGTERM → SIGKILL escalation; everything else (log close, metadata
        # write) is intentionally bare so its exceptions surface to the caller.
        try:
            _signal_process_group(process, signal.SIGTERM)
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _signal_process_group(process, signal.SIGKILL)
            process.wait(timeout=5)
        if log_handle is not None:
            try:
                log_handle.close()
            except OSError:
                pass
        if recording_dir is not None:
            metadata_path = recording_dir / "metadata.json"
            if metadata_path.exists():
                metadata = json.loads(metadata_path.read_text())
                metadata["recording_stopped_at"] = local_now().isoformat()
                metadata["duration"] = round(runtime._elapsed(), 3)
                metadata["status"] = "aborted"
                metadata["error"] = "script exited before stop_recording()"
                runtime._write_json(metadata_path, metadata)
    finally:
        _STATE.is_recording = False
        _STATE.process = None
        _STATE.log_handle = None
        _STATE.hud_process = None


def _intro_payload(value: str | dict | None) -> dict | None:
    if value is None:
        return None
    if isinstance(value, str):
        return {"title": value, "countdown": 5}
    return dict(value)
