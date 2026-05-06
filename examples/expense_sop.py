"""Safari/GitHub demo for Screen Harness.

Run from the project root:

    uv run screen-harness -c 'exec(open("examples/expense_sop.py").read())'
"""

from __future__ import annotations

import subprocess
from pathlib import Path


REPO_URL = "https://github.com/frankyxhl/screen-harness"


def open_repo_in_safari() -> None:
    safari_paths = [
        Path("/Applications/Safari.app"),
        Path.home() / "Applications/Safari.app",
    ]
    if any(path.exists() for path in safari_paths):
        subprocess.run(["open", "-a", "Safari", REPO_URL], check=False)
        return
    subprocess.run(["open", REPO_URL], check=False)


recording_dir = start_recording("safari_github_repo_demo")
intro(
    "This video demonstrates the Screen Harness GitHub repository",
    subtitle="Safari opens GitHub and reviews the project page.",
    countdown=5,
)

chapter("Open Screen Harness on GitHub")

step("Launch Safari", note="Open Safari for the repository walkthrough.")
caption("Open Safari and start the repository walkthrough.", duration=3.0)
open_repo_in_safari()
wait(3.0)

step("Visit the repository", note="Navigate directly to github.com/frankyxhl/screen-harness.")
caption("Navigate to github.com/frankyxhl/screen-harness.", duration=4.0)
highlight_region(150, 70, 1180, 70, text="Repository URL", duration=3.0, color="blue@0.35")
wait(3.0)

step("Review the project header", note="Confirm the repository name and top-level project context.")
caption("Confirm the Screen Harness repository page is open.", duration=4.0)
highlight_region(220, 145, 1120, 150, text="Repository header", duration=4.0, color="blue@0.35")
wait(3.0)

step("Inspect the files", note="Scan the README and file list to understand the MVP structure.")
caption("Use the README and file list to inspect the MVP structure.", duration=4.0)
highlight_region(230, 360, 980, 430, text="Project files", duration=4.0, color="blue@0.35")
wait(3.0)

stop_recording()
final_video = render(template="training")
print(f"recording: {recording_dir}")
print(f"final video: {final_video}")
