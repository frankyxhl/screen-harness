"""Unit tests for HUD JSON command protocol and state machine (pure Python, no AppKit)."""

from __future__ import annotations

import json

import pytest

from screen_harness.hud import HUDState, format_rec_time, parse_command


class TestParseCommand:
    def test_parse_start_command(self):
        line = json.dumps({
            "cmd": "start",
            "screen": {"av_index": 0, "av_name": "Capture screen 0",
                       "display_id": 1, "bounds": [0, 0, 1920, 1080],
                       "is_main": True, "backing_scale": 2.0},
            "region": [0, 0, 100, 100],
            "started_at": 1234567890.0,
        })
        result = parse_command(line)
        assert result["cmd"] == "start"
        assert result["region"] == [0, 0, 100, 100]
        assert result["started_at"] == pytest.approx(1234567890.0)

    def test_parse_stop_command(self):
        line = json.dumps({"cmd": "stop"})
        result = parse_command(line)
        assert result["cmd"] == "stop"

    def test_malformed_json_raises_value_error(self):
        with pytest.raises(ValueError):
            parse_command("{not valid json")

    def test_empty_string_raises_value_error(self):
        with pytest.raises(ValueError):
            parse_command("")

    def test_non_object_raises_value_error(self):
        with pytest.raises(ValueError):
            parse_command('"just a string"')

    def test_missing_cmd_raises_value_error(self):
        with pytest.raises(ValueError):
            parse_command('{"region": [0, 0, 100, 100]}')

    def test_unknown_cmd_raises_value_error(self):
        with pytest.raises(ValueError):
            parse_command('{"cmd": "unknown_command"}')


class TestHUDState:
    def test_initial_state_is_idle(self):
        state = HUDState()
        assert state.state == "idle"

    def test_start_from_idle_transitions_to_running(self):
        state = HUDState()
        cmd = {"cmd": "start", "screen": {}, "region": [0, 0, 100, 100], "started_at": 0.0}
        state.handle(cmd)
        assert state.state == "running"

    def test_stop_from_running_transitions_to_stopped(self):
        state = HUDState()
        state.handle({"cmd": "start", "screen": {}, "region": [0, 0, 100, 100], "started_at": 0.0})
        state.handle({"cmd": "stop"})
        assert state.state == "stopped"

    def test_start_from_running_is_idempotent(self):
        """Starting when already running should not raise and stay running."""
        state = HUDState()
        cmd = {"cmd": "start", "screen": {}, "region": [0, 0, 100, 100], "started_at": 0.0}
        state.handle(cmd)
        # Should not raise; stays running
        state.handle(cmd)
        assert state.state == "running"

    def test_stop_from_idle_is_no_op(self):
        """Stopping when idle should not raise."""
        state = HUDState()
        state.handle({"cmd": "stop"})
        assert state.state in ("idle", "stopped")

    def test_start_stores_region(self):
        state = HUDState()
        cmd = {"cmd": "start", "screen": {}, "region": [10, 20, 800, 600], "started_at": 5.0}
        state.handle(cmd)
        assert state.region == [10, 20, 800, 600]

    def test_start_stores_started_at(self):
        state = HUDState()
        cmd = {"cmd": "start", "screen": {}, "region": [0, 0, 100, 100], "started_at": 1234.5}
        state.handle(cmd)
        assert state.started_at == pytest.approx(1234.5)


class TestFormatRecTime:
    def test_zero(self):
        assert format_rec_time(0) == "00:00:00"

    def test_one_second(self):
        assert format_rec_time(1) == "00:00:01"

    def test_one_minute(self):
        assert format_rec_time(60) == "00:01:00"

    def test_one_hour(self):
        assert format_rec_time(3600) == "01:00:00"

    def test_hms_mixed(self):
        assert format_rec_time(3661) == "01:01:01"

    def test_large_hours(self):
        assert format_rec_time(36000) == "10:00:00"

    def test_59_minutes_59_seconds(self):
        assert format_rec_time(3599) == "00:59:59"


class TestParseStatusCommand:
    def test_parse_status_command(self):
        line = '{"cmd": "status"}'
        result = parse_command(line)
        assert result["cmd"] == "status"

    def test_hud_state_handles_status(self):
        state = HUDState()
        state.handle({"cmd": "start", "screen": {}, "region": [0, 0, 100, 100], "started_at": 0.0})
        state.handle({"cmd": "status"})
        assert state.state == "running"

    def test_start_then_status_reports_running(self):
        """State must reflect 'running' synchronously after handle(start).

        This is the pure-Python regression for the stdin-reader race: if start
        updates state synchronously (not deferred to AppKit thread), a status
        query immediately after sees 'running', not 'idle'.
        """
        state = HUDState()
        start_cmd = {"cmd": "start", "screen": {}, "region": [0, 0, 100, 100], "started_at": 0.0}
        state.handle(start_cmd)
        # Simulate what the status branch in the reader thread does:
        assert state.state == "running"
