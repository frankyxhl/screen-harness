"""Safari/GitHub demo for Screen Harness.

Run from the project root:

    uv run screen-harness -c 'exec(open("examples/expense_sop.py").read())'

The script:
  1. Activates Safari and forces a deterministic 1920x1080 layout.
  2. Reads back the actual window bounds (macOS clamps top to leave room for
     the menu bar) and uses them as the AVFoundation crop region, so only
     Safari is recorded — no Dock, no menu bar.
  3. Authors highlight rectangles in the cropped coordinate space.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


REPO_URL = "https://github.com/frankyxhl/screen-harness"


def _osascript(script: str) -> str:
    result = subprocess.run(
        ["osascript", "-e", script],
        check=False,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip()


def _safari_installed() -> bool:
    return any(
        path.exists()
        for path in (
            Path("/Applications/Safari.app"),
            Path.home() / "Applications/Safari.app",
        )
    )


def open_safari_and_get_region() -> tuple[int, int, int, int] | None:
    """Activate Safari at a known geometry and return the crop region."""
    if not _safari_installed():
        subprocess.run(["open", REPO_URL], check=False)
        return None
    subprocess.run(["open", "-a", "Safari", REPO_URL], check=False)
    _osascript('delay 0.7')
    _osascript(
        'tell application "Safari"\n'
        '  activate\n'
        '  if (count of windows) is 0 then make new document\n'
        '  set bounds of front window to {0, 0, 1920, 1080}\n'
        'end tell'
    )
    _osascript('delay 0.4')
    bounds = _osascript('tell application "Safari" to get bounds of front window')
    parts = [p.strip() for p in bounds.split(",")]
    if len(parts) != 4:
        return None
    try:
        x1, y1, x2, y2 = (int(p) for p in parts)
    except ValueError:
        return None
    return (x1, y1, x2 - x1, y2 - y1)


def scroll_safari(amount: int) -> None:
    _osascript(
        'tell application "Safari" to do JavaScript '
        f'"window.scrollBy({{top:{int(amount)}, behavior:\'smooth\'}})" '
        'in front document'
    )


region = open_safari_and_get_region()
# Once Safari is positioned, the script's coordinate system is the cropped
# Safari window: (0, 0) is the window's top-left.
recording_dir = start_recording("safari_github_repo_demo", region=region)
intro(
    "Screen Harness",
    subtitle="A 30-second tour of the repository on GitHub.",
    countdown=5,
)

chapter("Open Screen Harness on GitHub")

step("Open the repository", note="Launch Safari and load github.com/frankyxhl/screen-harness.")
caption("Launching Safari and loading the repository.", duration=4.0)
wait(4.0)

step("Find the URL", note="The unified address bar shows the repo path.")
caption("The unified address bar shows the repo path.", duration=4.0)
# Safari URL pill, in cropped (window-relative) coords.
highlight_region(540, 5, 820, 52, text="URL", duration=3.5, color="0x00ADB5@0.85", thickness=6)
wait(3.5)

step("Read the repo header", note="Owner, name, and visibility live here.")
caption("Owner, name, and visibility live here.", duration=4.0)
highlight_region(150, 125, 720, 42, text="Repo header", duration=3.5, color="0x00ADB5@0.85", thickness=6)
wait(3.5)

step("Scan the file list", note="The MVP keeps source, examples, tests, and rules side by side.")
caption("The MVP keeps source, examples, tests, and rules side by side.", duration=5.0)
highlight_region(355, 370, 990, 325, text="Files", duration=4.5, color="0x00ADB5@0.85", thickness=6)
wait(4.5)

step("Open the README", note="Scroll into the README to see install and demo instructions.")
caption("Scroll into the README to see install and demo instructions.", duration=5.0)
scroll_safari(900)
wait(2.0)
highlight_region(355, 355, 990, 340, text="README", duration=4.0, color="0x00ADB5@0.85", thickness=6)
wait(4.0)

outro(
    "Thanks for watching",
    subtitle="Find Screen Harness on GitHub",
    url="github.com/frankyxhl/screen-harness",
    duration=4.0,
)

stop_recording()
final_video = render(template="training")
print(f"recording: {recording_dir}")
print(f"final video: {final_video}")
