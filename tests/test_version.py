"""Lock the package's runtime `__version__` to whatever pyproject declares.

Before this regression test landed, `__init__.py` carried a hand-pinned
`__version__` constant that drifted from `pyproject.toml` between releases —
a stale `0.0.1` runtime constant alongside a `0.1.0` PyPI release. Deriving
from `importlib.metadata` gives one source of truth, and this test guards
the wiring so a future refactor cannot silently re-introduce the drift.
"""

from importlib.metadata import PackageNotFoundError, version as pkg_version
from pathlib import Path

import re

import screen_harness


def _pyproject_version() -> str:
    text = (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text()
    match = re.search(r'^version = "([^"]+)"', text, flags=re.MULTILINE)
    assert match, "pyproject.toml has no `version = \"…\"` line"
    return match.group(1)


def test_runtime_version_matches_pyproject():
    """When the package is installed (editable or wheel), `screen_harness.__version__`
    must match the version in `pyproject.toml`."""
    try:
        installed = pkg_version("screen-harness")
    except PackageNotFoundError:
        # No metadata available (e.g. plain source checkout). The fallback
        # sentinel below is what users would see, so make the contract explicit.
        assert screen_harness.__version__ == "0+unknown"
        return
    assert installed == _pyproject_version(), (
        f"installed metadata version {installed!r} does not match pyproject "
        f"{_pyproject_version()!r} — the wheel was built from a different tree"
    )
    assert screen_harness.__version__ == installed, (
        f"screen_harness.__version__ ({screen_harness.__version__!r}) drifted from "
        f"the installed metadata ({installed!r})"
    )
