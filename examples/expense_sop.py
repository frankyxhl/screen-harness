"""Chrome/GitHub demo for Screen Harness.

Run from the project root:

    uv run screen-harness -c 'exec(open("examples/expense_sop.py").read())'
"""

from __future__ import annotations

import subprocess
from pathlib import Path


REPO_URL = "https://github.com/frankyxhl/screen-harness"


def open_repo_in_chrome() -> None:
    chrome_paths = [
        Path("/Applications/Google Chrome.app"),
        Path.home() / "Applications/Google Chrome.app",
    ]
    if any(path.exists() for path in chrome_paths):
        subprocess.run(["open", "-na", "Google Chrome", "--args", "--new-window", REPO_URL], check=False)
        return
    subprocess.run(["open", REPO_URL], check=False)


recording_dir = start_recording("chrome_github_repo_demo")

chapter("Open Screen Harness on GitHub")

step("Launch Chrome")
caption("Open Google Chrome and start a fresh browser window.", duration=3.0)
open_repo_in_chrome()
wait(3.0)

step("Visit the repository")
caption("Navigate to github.com/frankyxhl/screen-harness.", duration=4.0)
highlight_region(150, 70, 1180, 70, text="Repository URL", duration=3.0)
wait(3.0)

step("Review the project header")
caption("Confirm the Screen Harness repository page is open.", duration=4.0)
highlight_region(220, 145, 1120, 150, text="Repository header", duration=4.0)
wait(3.0)

step("Inspect the files")
caption("Use the README and file list to inspect the MVP structure.", duration=4.0)
highlight_region(230, 360, 980, 430, text="Project files", duration=4.0)
wait(3.0)

stop_recording()
final_video = render()
print(f"recording: {recording_dir}")
print(f"final video: {final_video}")
