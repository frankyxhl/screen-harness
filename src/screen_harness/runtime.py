"""Shared runtime state for the agent-facing helper API.

`_STATE` is the single mutable singleton the recording lifecycle, the script
API, and the render orchestrator all consult. Modules must read it as
``runtime._STATE`` (module-attribute lookup) so tests can swap it with
``monkeypatch.setattr(runtime, "_STATE", ...)`` in one place.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import IO

from .metadata import write_text_atomic
from .timeline import Timeline


@dataclass
class RuntimeState:
    root: Path
    recording_dir: Path | None = None
    timeline: Timeline | None = None
    started_at: float | None = None
    process: subprocess.Popen | None = None
    log_handle: IO[str] | None = None
    is_recording: bool = False
    screen_inventory: list | None = None  # cached probe_screens() result
    hud_process: subprocess.Popen | None = None  # optional HUD subprocess


_STATE = RuntimeState(root=Path.cwd())


def configure(root: Path) -> None:
    global _STATE
    _STATE = RuntimeState(root=Path(root))


def load_agent_helpers(workspace: Path, namespace: dict) -> None:
    helper_file = Path(workspace) / "agent_helpers.py"
    if not helper_file.exists():
        return
    spec = importlib.util.spec_from_file_location("screen_harness_agent_helpers", helper_file)
    if not spec or not spec.loader:
        return
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name, value in vars(module).items():
        if not name.startswith("_"):
            namespace[name] = value


def _timeline() -> Timeline:
    if not _STATE.timeline:
        raise RuntimeError("start_recording() must be called first")
    return _STATE.timeline


def _recording_dir() -> Path:
    if not _STATE.recording_dir:
        raise RuntimeError("no recording directory is active")
    return _STATE.recording_dir


def _event_time(t: float | None) -> float:
    return _elapsed() if t is None else float(t)


def _elapsed() -> float:
    if _STATE.started_at is None:
        return 0.0
    return time.monotonic() - _STATE.started_at


def _write_json(path: Path, data: dict) -> None:
    write_text_atomic(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
