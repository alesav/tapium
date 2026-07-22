"""
Tests for tapium.py's CLI entry point (`main()`), exercised via subprocess
so they run exactly the way a real caller would invoke the tool. Only
covers the validation paths that fail BEFORE connecting to a device (no
args, invalid JSON, unknown action) — anything past that point requires a
real device/emulator and is out of scope for this suite.
"""

import json
import os
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAPIUM = os.path.join(REPO_ROOT, "tapium.py")


def run(*args):
    return subprocess.run(
        [sys.executable, TAPIUM, *args],
        capture_output=True, text=True,
    )


def test_no_arguments_reports_usage_error():
    proc = run()
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["ok"] is False
    assert "No action provided" in payload["error"]


def test_invalid_json_reports_parse_error():
    proc = run("{not valid json")
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["ok"] is False
    assert "Invalid JSON" in payload["error"]


def test_unknown_action_lists_available_actions():
    proc = run('{"action":"teleport"}')
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["ok"] is False
    assert "teleport" in payload["error"]
    assert "tap" in payload["available"]
    assert "dump_ui" in payload["available"]


def test_missing_action_key_is_treated_as_unknown():
    proc = run('{"text":"Sign in"}')
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["ok"] is False
