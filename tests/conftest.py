"""
Shared pytest fixtures for the Tapium test suite.

Inserts the repo root onto sys.path so `import tapium` works regardless of
the directory pytest is invoked from, and provides a lightweight FakeDevice
standing in for a real uiautomator2.Device — no real Android device or
emulator is needed to run these tests.
"""

import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)


class FakeUIObject:
    """Stands in for the object returned by uiautomator2's `d(text=...)`
    selector call — the small subset of its API tapium.py actually uses."""

    def __init__(self, exists=True, bounds=None):
        self._exists = exists
        self._bounds = bounds or {"left": 100, "top": 200, "right": 300, "bottom": 400}

    def wait(self, timeout=0):
        return self._exists

    def exists(self, timeout=0):
        return self._exists

    def click(self):
        pass

    @property
    def info(self):
        return {"bounds": self._bounds}


class FakeDevice:
    """Minimal stand-in for uiautomator2.Device covering every method
    tapium.py's action_* functions call. Records every call made on it in
    `.calls` so tests can assert on what would have happened on a real
    device, without needing one connected."""

    def __init__(self, xml="<hierarchy></hierarchy>", width=1080, height=2400,
                 selector_result=None):
        self.xml = xml
        self.info = {"displayWidth": width, "displayHeight": height}
        self.calls = []
        self._selector_result = selector_result or FakeUIObject()

    def dump_hierarchy(self):
        return self.xml

    def wait_idle(self, timeout=2.0):
        self.calls.append(("wait_idle", timeout))

    def click(self, x, y):
        self.calls.append(("click", x, y))

    def send_keys(self, text):
        self.calls.append(("send_keys", text))

    def clear_text(self):
        self.calls.append(("clear_text",))

    def swipe(self, x1, y1, x2, y2, duration=0.3):
        self.calls.append(("swipe", x1, y1, x2, y2, duration))

    def drag(self, x1, y1, x2, y2, duration=0.5):
        self.calls.append(("drag", x1, y1, x2, y2, duration))

    def gesture(self, *args, **kwargs):
        self.calls.append(("gesture", args, kwargs))

    def press(self, key):
        self.calls.append(("press", key))

    def screenshot(self, path):
        self.calls.append(("screenshot", path))

    def app_clear(self, package):
        self.calls.append(("app_clear", package))

    def app_start(self, package):
        self.calls.append(("app_start", package))

    def app_uninstall(self, package):
        self.calls.append(("app_uninstall", package))
        return True

    def __call__(self, **kwargs):
        self.calls.append(("selector", kwargs))
        return self._selector_result


@pytest.fixture
def fake_device():
    return FakeDevice()
