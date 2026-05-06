"""Screen Harness package."""

from importlib.metadata import PackageNotFoundError, version as _pkg_version

try:
    __version__ = _pkg_version("screen-harness")
except PackageNotFoundError:
    # Editable install with no installed metadata yet (e.g. running tests
    # straight from the source tree). Fall back to a sentinel rather than
    # silently drifting from `pyproject.toml`.
    __version__ = "0+unknown"
