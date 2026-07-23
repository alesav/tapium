"""
test_login_example.py — TC-001 (see test-cases.md) turned into a real
pytest test. This is the pattern to follow when promoting any entry
from test-cases.md into automated coverage: each documented step
becomes one Tapium action call, each expected result becomes an
assertion on "ok" or on the returned "screen" contents.

Fill in PACKAGE_NAME, TEST_EMAIL, TEST_PASSWORD, and HOME_LANDMARK_TEXT
for your app before running.

Run:
    pytest test_login_example.py -v
"""

import pytest
import tapium as agent

PACKAGE_NAME = "com.example.app"
TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "hunter2"
HOME_LANDMARK_TEXT = "Home"  # an element that only appears once logged in


@pytest.fixture
def device():
    d = agent.connect()
    agent.ensure_screen_on(d)
    return d


def test_login_positive(device):
    # Precondition: clean state, lands on the Login screen
    reset_result = agent.action_reset_app(device, {"package": PACKAGE_NAME})
    assert reset_result["ok"], f"Could not reset app: {reset_result}"

    # Fill both fields and submit in one call
    result = agent.action_input_sequence(device, {
        "steps": [
            {"field": "Email", "text": TEST_EMAIL},
            {"field": "Password", "text": TEST_PASSWORD},
            {"tap_text": "Log in"},
        ]
    })
    assert result["ok"], f"Login form submission failed: {result}"

    # Expected result: Home screen loads within 15s
    result = agent.action_wait_for(device, {"text": HOME_LANDMARK_TEXT, "timeout": 15})
    assert result["ok"], (
        f"Did not land on Home screen after login. "
        f"Last screen contents: {result.get('screen')}"
    )
