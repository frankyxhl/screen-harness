"""CLI entrypoint for Screen Harness."""

from __future__ import annotations

import sys
from difflib import unified_diff
from pathlib import Path

from . import helpers as helper_api
from .admin import run_doctor
from .captions import generate_caption_assets
from .recorder import record_screen
from .redact import scan_redactions
from .project import DEFAULT_AGENT_HELPERS, init_project
from .render import render_smoke
from .sop import generate_ai_sop
from .timeline import TimelineError
from .transcribe import transcribe_recording


HELP = """Screen Harness

Commands:
  screen-harness doctor
  screen-harness init
  screen-harness probe-screens [--json]
  screen-harness -c '<python>'
  screen-harness render <recording_id> [--template debug|training]
  screen-harness sop generate <recording_id>
  screen-harness sop ai-generate <recording_id>
  screen-harness transcribe <recording_id> [--provider manual]
  screen-harness redact scan <recording_id>
  screen-harness helpers diff|open|reset
  screen-harness spike render-smoke [work-dir]
  screen-harness spike record [output] [duration]
"""


def main() -> None:
    try:
        _dispatch()
    except TimelineError as exc:
        # timeline.json is hand-editable; a validation failure is a user
        # input problem, not a crash — print one line, no traceback.
        raise SystemExit(str(exc)) from exc


def _dispatch() -> None:
    args = sys.argv[1:]
    if not args or args[0] in {"-h", "--help"}:
        print(HELP)
        return
    if args[0] == "doctor":
        raise SystemExit(run_doctor())
    if args[0] == "probe-screens":
        _run_probe_screens(args[1:])
        return
    if args[0] == "init":
        init_project(Path.cwd())
        print("initialized screen-harness workspace")
        return
    if args[0] == "-c":
        if len(args) < 2:
            raise SystemExit("Usage: screen-harness -c '<python>'")
        root = Path.cwd()
        init_project(root)
        helper_api.configure(root)
        namespace = {name: getattr(helper_api, name) for name in helper_api.__all__}
        helper_api.load_agent_helpers(root / "agent-workspace", namespace)
        try:
            exec(args[1], namespace)
        except BaseException:
            helper_api.abort_active_recording()
            raise
        return
    if args[0] == "render" and len(args) >= 2:
        final = helper_api.render(_recording_dir(args[1]), template=_template_arg(args[2:]))
        print(final)
        return
    if args[:2] == ["sop", "generate"] and len(args) >= 3:
        outputs = generate_caption_assets(_recording_dir(args[2]))
        print(outputs.markdown)
        return
    if args[:2] == ["sop", "ai-generate"] and len(args) >= 3:
        try:
            outputs = generate_ai_sop(_recording_dir(args[2]))
        except FileNotFoundError as exc:
            raise SystemExit(str(exc)) from exc
        print(outputs.captions.markdown)
        return
    if args[0] == "transcribe" and len(args) >= 2:
        outputs = transcribe_recording(_recording_dir(args[1]), provider_name=_provider_arg(args[2:]))
        print(outputs.transcript_srt)
        return
    if args[:2] == ["redact", "scan"] and len(args) >= 3:
        outputs = scan_redactions(_recording_dir(args[2]))
        print(outputs.suggestions)
        return
    if args[:2] == ["helpers", "open"]:
        print(Path.cwd() / "agent-workspace" / "agent_helpers.py")
        return
    if args[:2] == ["helpers", "reset"]:
        init_project(Path.cwd())
        (Path.cwd() / "agent-workspace" / "agent_helpers.py").write_text(DEFAULT_AGENT_HELPERS)
        print("reset agent_helpers.py")
        return
    if args[:2] == ["helpers", "diff"]:
        init_project(Path.cwd())
        path = Path.cwd() / "agent-workspace" / "agent_helpers.py"
        diff = unified_diff(DEFAULT_AGENT_HELPERS.splitlines(True), path.read_text().splitlines(True), fromfile="default", tofile=str(path))
        print("".join(diff), end="")
        return
    if args[:2] == ["spike", "render-smoke"]:
        work_dir = Path(args[2]) if len(args) > 2 else Path(".screen-harness-spike")
        result = render_smoke(work_dir)
        print(result.stdout, end="")
        print(f"render smoke output: {work_dir / 'final.mp4'}")
        raise SystemExit(result.returncode)
    if args[:2] == ["spike", "record"]:
        output = Path(args[2]) if len(args) > 2 else Path(".screen-harness-spike/raw.mp4")
        duration = float(args[3]) if len(args) > 3 else 30.0
        result = record_screen(output, duration=duration)
        print(result.stdout, end="")
        print(f"record output: {output}")
        raise SystemExit(result.returncode)
    raise SystemExit(HELP)


def _run_probe_screens(args: list[str]) -> None:
    import json as _json
    from dataclasses import asdict
    from .screens import ScreenProbeError, probe_screens

    as_json = "--json" in args
    try:
        screens = probe_screens()
    except ScreenProbeError as exc:
        raise SystemExit(f"probe-screens failed: {exc}") from exc

    if as_json:
        print(_json.dumps([asdict(s) for s in screens], ensure_ascii=False, indent=2))
    else:
        if not screens:
            print("No screen devices found — check Screen Recording permission.")
        for s in screens:
            main_marker = "  MAIN" if s.is_main else ""
            print(f"  [{s.av_index}] {s.av_name}  display_id={s.display_id} bounds={s.bounds}{main_marker}")


def _recording_dir(recording_id: str) -> Path:
    path = Path(recording_id)
    if (path.is_absolute() or len(path.parts) > 1) and path.exists():
        return path
    return Path.cwd() / "recordings" / recording_id


def _provider_arg(args: list[str]) -> str:
    if not args:
        return "manual"
    if len(args) == 2 and args[0] == "--provider":
        return args[1]
    raise SystemExit("Usage: screen-harness transcribe <recording_id> [--provider manual]")


def _template_arg(args: list[str]) -> str | None:
    if not args:
        return None
    if len(args) == 2 and args[0] == "--template":
        return args[1]
    raise SystemExit("Usage: screen-harness render <recording_id> [--template debug|training]")


if __name__ == "__main__":
    main()
