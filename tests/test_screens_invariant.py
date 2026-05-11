"""macOS-gated integration test: AV↔CGDirectDisplayID binding invariant.

Skipped on non-macOS or when PyObjC is absent.
"""

from __future__ import annotations

import platform

import pytest


def _pyobjc_present() -> bool:
    try:
        import Quartz  # noqa: F401
        return True
    except ImportError:
        return False


_on_macos = platform.system() == "Darwin"

macos_only = pytest.mark.skipif(
    not _on_macos,
    reason="macOS-only test (requires Quartz + AVFoundation)",
)


@pytest.mark.macos
@macos_only
def test_probe_screens_real_host_at_least_one_screen():
    """On a real Mac, probe returns at least one screen device."""
    from screen_harness.screens import probe_screens

    screens = probe_screens()
    assert len(screens) >= 1, "Expected at least one screen device from real host"
    if _pyobjc_present():
        for s in screens:
            assert s.display_id != 0, f"Screen {s.av_name} has null display_id"


@pytest.mark.macos
@macos_only
def test_probe_screens_no_cameras_returned():
    """probe_screens() must return only screen devices, never cameras."""
    from screen_harness.screens import probe_screens

    screens = probe_screens()
    for s in screens:
        if _pyobjc_present():
            assert s.display_id != 0, (
                f"Device [{s.av_index}] {s.av_name!r} returned display_id=0 "
                "— possible camera mis-classification"
            )
