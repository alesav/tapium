"""
Tests for a representative slice of tapium.py's action_* functions, using
the FakeDevice from conftest.py in place of a real uiautomator2.Device.
These aren't exhaustive over every action (some, like action_install_app
and action_set_location, are heavily side-effecting and real-device
dependent — lower value to unit test) but cover the core tap/type/swipe/
wait_for surface plus every action's own input-validation error paths.
"""

from conftest import FakeDevice, FakeUIObject
import tapium


# ── action_tap ────────────────────────────────────────────────────────────────

def test_action_tap_by_text_clicks_computed_center():
    xml = """<hierarchy>
      <node text="Sign in" content-desc="" class="android.widget.Button"
            clickable="true" bounds="[100,200][300,260]" />
    </hierarchy>"""
    d = FakeDevice(xml=xml)
    result = tapium.action_tap(d, {"text": "Sign in"})
    assert result["ok"] is True
    assert result["coords"] == [200, 230]
    assert ("click", 200, 230) in d.calls


def test_action_tap_by_coords_bypasses_lookup():
    d = FakeDevice()
    result = tapium.action_tap(d, {"coords": [540, 1200]})
    assert result["ok"] is True
    assert ("click", 540, 1200) in d.calls


def test_action_tap_missing_element_fails_cleanly():
    d = FakeDevice(xml="<hierarchy></hierarchy>")
    result = tapium.action_tap(d, {"text": "Nope"})
    assert result["ok"] is False
    assert "not found" in result["error"]


def test_action_tap_requires_text_or_coords():
    result = tapium.action_tap(None, {})
    assert result["ok"] is False
    assert "requires" in result["error"]


# ── action_input_text ─────────────────────────────────────────────────────────

def test_action_input_text_requires_text():
    result = tapium.action_input_text(None, {})
    assert result["ok"] is False
    assert "requires" in result["error"]


def test_action_input_text_sends_keys_without_a_field():
    d = FakeDevice()
    result = tapium.action_input_text(d, {"text": "hello@example.com"})
    assert result["ok"] is True
    assert ("send_keys", "hello@example.com") in d.calls


def test_action_input_text_clears_before_typing_when_requested():
    d = FakeDevice()
    tapium.action_input_text(d, {"text": "new value", "clear": True})
    assert ("clear_text",) in d.calls
    # clear must happen before the new text is sent
    clear_idx = d.calls.index(("clear_text",))
    send_idx = d.calls.index(("send_keys", "new value"))
    assert clear_idx < send_idx


def test_action_input_text_focuses_field_by_hint_first():
    xml = """<hierarchy>
      <node text="" content-desc="" class="android.widget.EditText" hint="Email"
            clickable="true" bounds="[50,300][1000,360]" />
    </hierarchy>"""
    d = FakeDevice(xml=xml)
    result = tapium.action_input_text(d, {"field": "Email", "text": "a@b.com"})
    assert result["ok"] is True
    # (50+1000)//2, (300+360)//2
    assert ("click", 525, 330) in d.calls


def test_action_input_text_reports_error_when_field_not_found():
    d = FakeDevice(xml="<hierarchy></hierarchy>")
    result = tapium.action_input_text(d, {"field": "Nope", "text": "x"})
    assert result["ok"] is False
    assert "Nope" in result["error"]


# ── action_swipe ──────────────────────────────────────────────────────────────

def test_action_swipe_up_uses_upper_and_lower_quarter_of_screen():
    d = FakeDevice(width=1080, height=2400)
    result = tapium.action_swipe(d, {"direction": "up"})
    assert result["ok"] is True
    cx = 540
    assert ("swipe", cx, 1800, cx, 600, 0.3) in d.calls


def test_action_swipe_rejects_unknown_direction():
    d = FakeDevice()
    result = tapium.action_swipe(d, {"direction": "diagonal"})
    assert result["ok"] is False
    assert "Unknown direction" in result["error"]


# ── action_drag / action_pinch ────────────────────────────────────────────────

def test_action_drag_requires_start_and_end():
    result = tapium.action_drag(None, {"start": [0, 0]})
    assert result["ok"] is False
    assert "requires" in result["error"]


def test_action_drag_calls_device_drag_with_given_points():
    d = FakeDevice()
    result = tapium.action_drag(d, {"start": [10, 20], "end": [30, 40], "duration": 0.9})
    assert result["ok"] is True
    assert ("drag", 10, 20, 30, 40, 0.9) in d.calls


def test_action_pinch_rejects_invalid_direction():
    result = tapium.action_pinch(None, {"direction": "sideways"})
    assert result["ok"] is False
    assert "in" in result["error"] or "out" in result["error"]


def test_action_pinch_out_spreads_points_apart():
    d = FakeDevice(width=1000, height=1000)
    result = tapium.action_pinch(d, {"direction": "out", "percent": 100})
    assert result["ok"] is True
    gesture_call = next(c for c in d.calls if c[0] == "gesture")
    (start1, start2, end1, end2), _kwargs = gesture_call[1], gesture_call[2]
    start_span = abs(start2[0] - start1[0])
    end_span = abs(end2[0] - end1[0])
    assert end_span > start_span  # fingers end up farther apart than they started


# ── action_press_key ──────────────────────────────────────────────────────────

def test_action_press_key_rejects_unknown_key():
    result = tapium.action_press_key(None, {"key": "volume_up"})
    assert result["ok"] is False
    assert "Unknown key" in result["error"]


def test_action_press_key_presses_known_key():
    d = FakeDevice()
    result = tapium.action_press_key(d, {"key": "back"})
    assert result["ok"] is True
    assert ("press", "back") in d.calls


# ── action_wait_for ───────────────────────────────────────────────────────────

def test_action_wait_for_success():
    d = FakeDevice(selector_result=FakeUIObject(exists=True))
    result = tapium.action_wait_for(d, {"text": "Home", "timeout": 1})
    assert result["ok"] is True
    assert result["found"] == "Home"


def test_action_wait_for_timeout_reports_failure():
    d = FakeDevice(selector_result=FakeUIObject(exists=False))
    result = tapium.action_wait_for(d, {"text": "Never Appears", "timeout": 0.01})
    assert result["ok"] is False
    assert "did not appear" in result["error"]


def test_action_wait_for_requires_text():
    result = tapium.action_wait_for(None, {})
    assert result["ok"] is False
    assert "requires" in result["error"]


# ── action_reset_app / action_uninstall_app ──────────────────────────────────

def test_action_reset_app_requires_package():
    result = tapium.action_reset_app(None, {})
    assert result["ok"] is False
    assert "requires" in result["error"]


def test_action_reset_app_clears_and_relaunches():
    d = FakeDevice()
    result = tapium.action_reset_app(d, {"package": "com.example.app"})
    assert result["ok"] is True
    assert ("app_clear", "com.example.app") in d.calls
    assert ("app_start", "com.example.app") in d.calls


def test_action_uninstall_app_requires_package():
    result = tapium.action_uninstall_app(None, {})
    assert result["ok"] is False


def test_action_uninstall_app_calls_device():
    d = FakeDevice()
    result = tapium.action_uninstall_app(d, {"package": "com.example.app"})
    assert result["ok"] is True
    assert ("app_uninstall", "com.example.app") in d.calls
