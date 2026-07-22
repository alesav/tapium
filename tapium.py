#!/usr/bin/env python3
"""
tapium.py — AI-agent-friendly Android controller via uiautomator2.

A single-file, dependency-light CLI for letting an LLM agent drive a real
Android device (or emulator) over USB/ADB. Every action waits for the
screen to settle before returning, so the caller always gets a fresh UI
dump in the same response — no polling loop, no fixed sleeps required
on the caller's side.

Usage:
    python tapium.py '<json_action>'

All responses are JSON printed to stdout.

Actions:
    tap            {"action":"tap","text":"label"}  |  {"action":"tap","coords":[x,y]}
    input_text     {"action":"input_text","text":"..."}
                   {"action":"input_text","field":"Email","text":"..."}        ← tap-then-type
                   {"action":"input_text","field":"Password","text":"...","clear":true}
    input_sequence {"action":"input_sequence","steps":[...]}                   ← fill a whole form in one call
    clear_text     {"action":"clear_text"}  |  {"action":"clear_text","field":"Email"}
    swipe          {"action":"swipe","direction":"up|down|left|right"}
    drag           {"action":"drag","start":[x1,y1],"end":[x2,y2],"duration":0.5}
    pinch          {"action":"pinch","direction":"out","percent":80,"steps":50}     ← zoom in
                   {"action":"pinch","direction":"in","percent":80,"steps":50}      ← zoom out
                   {"action":"pinch","direction":"out","center":[x,y],"percent":50}
    press_key      {"action":"press_key","key":"back|home|recent|enter"}
    wait_for       {"action":"wait_for","text":"label","timeout":10}
    screenshot     {"action":"screenshot","path":"/tmp/screen.png"}
    dump_ui        {"action":"dump_ui"}
    screen_on      {"action":"screen_on"}
    tap_selector   {"action":"tap_selector","className":"...","instance":2}
    reset_app      {"action":"reset_app","package":"com.example.app"}
                   {"action":"reset_app","package":"com.example.app","landmark_text":"Welcome"}
    uninstall_app  {"action":"uninstall_app","package":"com.example.app"}
    install_app    {"action":"install_app","apk_path":"/path/to/app.apk"}
                   {"action":"install_app","apk_path":"...","package":"com.example.app","launch":true}
    set_location   {"action":"set_location","lat":51.919495,"lon":4.475682}
                   {"action":"set_location","stop":true}
                   ← requires a mock-location app installed and selected under
                     Developer Options; see README for setup notes.

This module deliberately knows nothing about any particular app. Anything
app-specific (package name, landmark screen text, APK paths) is passed in
as a parameter by the caller rather than hardcoded here.
"""

import sys
import json
import time
import re
import subprocess
import xml.etree.ElementTree as ET

import uiautomator2 as u2

# ── constants ────────────────────────────────────────────────────────────────
DEFAULT_IDLE_TIMEOUT    = 2.0   # seconds to wait for UI to go idle after action
DEFAULT_ELEMENT_TIMEOUT = 8.0   # seconds to wait for an element to appear
SCREEN_SETTLE_SLEEP     = 0.1   # short sleep after idle before dumping (renders)
DEFAULT_INSTALL_TIMEOUT = 180   # seconds to wait for an `adb install` to finish


# ── device connection ─────────────────────────────────────────────────────────
def connect() -> u2.Device:
    return u2.connect()   # auto-detects USB-connected device


def ensure_screen_on(d: u2.Device) -> bool:
    """
    Keeps the screen awake during automation by temporarily setting the
    screen-off timeout to its maximum, then sending KEYCODE_WAKEUP to
    un-dim if needed. No screen-state detection required — safe to call
    even if the screen is already on.

    Returns True if a wake keyevent was sent.
    """
    try:
        subprocess.run(
            ["adb", "shell", "settings", "put", "system",
             "screen_off_timeout", "1800000"],
            timeout=3
        )
    except Exception:
        pass

    try:
        subprocess.run(
            ["adb", "shell", "input", "keyevent", "KEYCODE_WAKEUP"],
            timeout=3
        )
        time.sleep(0.5)
    except Exception:
        d.screen_on()
        time.sleep(0.5)

    return True


# ── screen settle helpers ─────────────────────────────────────────────────────
def wait_idle(d: u2.Device, timeout: float = DEFAULT_IDLE_TIMEOUT) -> None:
    """Wait until the UI thread is idle (no animation / layout happening)."""
    try:
        d.wait_idle(timeout=timeout)
    except Exception:
        pass  # some devices don't support this; fall through
    time.sleep(SCREEN_SETTLE_SLEEP)


def _parse_ui(d: u2.Device) -> list:
    """Dump and parse the current UI into a compact list of elements."""
    xml = d.dump_hierarchy()
    root = ET.fromstring(xml)
    elements = []
    for node in root.iter():
        text       = node.attrib.get("text", "").strip()
        desc       = node.attrib.get("content-desc", "").strip()
        cls        = node.attrib.get("class", "").split(".")[-1]
        clickable  = node.attrib.get("clickable") == "true"
        scrollable = node.attrib.get("scrollable") == "true"
        bounds     = node.attrib.get("bounds", "")
        label      = text or desc
        if label:
            elements.append({
                "type":       cls,
                "text":       label,
                "bounds":     bounds,
                "clickable":  clickable,
                "scrollable": scrollable,
            })
    return elements


def _bounds_center(bounds_str: str):
    """Parse '[x1,y1][x2,y2]' → center (cx, cy), or None on failure."""
    try:
        nums = list(map(int, re.findall(r"\d+", bounds_str)))
        if len(nums) == 4:
            return (nums[0] + nums[2]) // 2, (nums[1] + nums[3]) // 2
    except Exception:
        pass
    return None


def _find_element(d: u2.Device, label: str):
    """Find the best matching element in the XML dump by text or description.

    Always returns the parsed XML node (`.attrib.get("bounds")` is a
    string) rather than uiautomator2's own `.info` dict — the two are not
    interchangeable, and `_bounds_center()` expects the string form.
    """
    xml = d.dump_hierarchy()
    root = ET.fromstring(xml)

    candidates = []
    for node in root.iter():
        text = node.attrib.get("text", "").strip()
        desc = node.attrib.get("content-desc", "").strip()
        if text == label or desc == label:
            candidates.append(node)

    if not candidates:
        return None

    for node in candidates:
        if node.attrib.get("clickable") == "true":
            return node
    for node in candidates:
        if node.attrib.get("enabled") == "true":
            return node
    return candidates[0]


def _wait_for_enabled(d: u2.Device, label: str, timeout: float = 8.0, interval: float = 0.5) -> bool:
    """
    Poll until an element matching `label` exists and has enabled='true',
    or timeout. Useful for toggle buttons where the underlying state
    change is asynchronous — the element can vanish from the dump
    entirely for a few seconds mid-transition before settling, so a
    fixed sleep risks moving on before the toggle has actually taken
    effect even though the tap itself landed.
    """
    elapsed = 0.0
    while elapsed < timeout:
        node = _find_element(d, label)
        if node is not None and node.attrib.get("enabled") == "true":
            return True
        time.sleep(interval)
        elapsed += interval
    return False


# ── actions ───────────────────────────────────────────────────────────────────
def action_tap(d: u2.Device, params: dict) -> dict:
    if "text" in params:
        label = params["text"]

        node = _find_element(d, label)
        if node is None:
            return {"ok": False, "error": f"Element '{label}' not found on screen"}

        bounds = node.attrib.get("bounds", "")
        center = _bounds_center(bounds)
        if center is None:
            return {"ok": False, "error": f"Could not parse bounds '{bounds}' for '{label}'"}

        cx, cy = center
        # Direct coordinate tap — bypasses the accessibility layer, works
        # with apps that ignore el.click() / AccessibilityAction.
        d.click(cx, cy)
        wait_idle(d)

        return {"ok": True, "tapped": label, "coords": [cx, cy], "screen": _parse_ui(d)}

    elif "coords" in params:
        x, y = params["coords"]
        d.click(x, y)
        wait_idle(d)
        return {"ok": True, "tapped": [x, y], "screen": _parse_ui(d)}

    return {"ok": False, "error": "tap requires 'text' or 'coords'"}


def _focus_field(d: u2.Device, field_label: str):
    """
    Tap a field by label to focus it before typing.
    Tries EditText first, then any clickable element matching the label.
    Returns an error dict on failure, None on success.
    """
    xml = d.dump_hierarchy()
    root = ET.fromstring(xml)

    # Strategy 1: an EditText whose hint/text/desc matches
    for node in root.iter():
        cls  = node.attrib.get("class", "")
        text = node.attrib.get("text", "").strip()
        desc = node.attrib.get("content-desc", "").strip()
        hint = node.attrib.get("hint", "").strip()
        if "EditText" in cls and (text == field_label or desc == field_label or hint == field_label):
            center = _bounds_center(node.attrib.get("bounds", ""))
            if center:
                d.click(*center)
                wait_idle(d)
                return None

    # Strategy 2: any clickable container whose label matches
    for node in root.iter():
        text = node.attrib.get("text", "").strip()
        desc = node.attrib.get("content-desc", "").strip()
        if (text == field_label or desc == field_label) and node.attrib.get("clickable") == "true":
            center = _bounds_center(node.attrib.get("bounds", ""))
            if center:
                d.click(*center)
                wait_idle(d)
                return None

    return {"ok": False, "error": f"Could not find field '{field_label}' to focus"}


def action_input_text(d: u2.Device, params: dict) -> dict:
    """
    Type text, optionally tapping a field first to focus it.

    Simple (field already focused):
        {"action":"input_text","text":"hello@example.com"}

    Tap-then-type (recommended):
        {"action":"input_text","field":"Email","text":"hello@example.com"}
        {"action":"input_text","field":"Password","text":"secret","clear":true}
    """
    text  = params.get("text", "")
    field = params.get("field")
    clear = params.get("clear", False)

    if not text:
        return {"ok": False, "error": "input_text requires 'text'"}

    if field:
        err = _focus_field(d, field)
        if err:
            return err

    if clear:
        d.clear_text()
        time.sleep(0.2)

    d.send_keys(text)
    wait_idle(d)
    return {"ok": True, "field": field, "typed": text, "screen": _parse_ui(d)}


def action_input_sequence(d: u2.Device, params: dict) -> dict:
    """
    Fill multiple fields and optionally tap a final button — all in one call.
    Avoids per-step round-trip overhead for forms where the screen does not
    change between field inputs.

    Usage:
        {
          "action": "input_sequence",
          "steps": [
            {"field": "Email",    "text": "user@example.com"},
            {"field": "Password", "text": "secret"},
            {"tap_coords": [540, 1024]}
          ]
        }

    Each step supports:
        field       — label of the EditText/field to focus before typing
        text        — text to type into the focused field
        clear       — (bool, default false) clear field before typing
        tap_coords  — [x, y] coordinate tap (e.g. a button hidden behind the keyboard)
        tap_text    — element label to tap (alternative to tap_coords)

    Returns a single screen dump from after the last step. Partial results
    are returned on first failure so the caller can diagnose.
    """
    steps = params.get("steps")
    if not steps or not isinstance(steps, list):
        return {"ok": False, "error": "input_sequence requires a 'steps' list"}

    completed = []
    for i, step in enumerate(steps):
        if "tap_coords" in step:
            x, y = step["tap_coords"]
            d.click(x, y)
            wait_idle(d)
            completed.append({"tap_coords": [x, y]})
            continue

        if "tap_text" in step:
            label = step["tap_text"]
            node = _find_element(d, label)
            if node is None:
                return {
                    "ok": False,
                    "error": f"Step {i}: element '{label}' not found",
                    "completed": completed,
                    "screen": _parse_ui(d),
                }
            center = _bounds_center(node.attrib.get("bounds", ""))
            if not center:
                return {
                    "ok": False,
                    "error": f"Step {i}: could not parse bounds for '{label}'",
                    "completed": completed,
                    "screen": _parse_ui(d),
                }
            d.click(*center)
            wait_idle(d)
            completed.append({"tap_text": label})
            continue

        field = step.get("field")
        text  = step.get("text", "")
        clear = step.get("clear", False)

        if not text:
            return {
                "ok": False,
                "error": f"Step {i}: 'text' is required for field input",
                "completed": completed,
            }

        if field:
            err = _focus_field(d, field)
            if err:
                err["completed"] = completed
                err["error"] = f"Step {i}: {err['error']}"
                return err

        if clear:
            d.clear_text()
            time.sleep(0.1)

        d.send_keys(text)
        # Short settle — the screen is NOT navigating between field inputs,
        # so skip the full wait_idle and just let the keyboard/IME catch up.
        time.sleep(0.15)
        completed.append({"field": field, "typed": text})

    wait_idle(d)
    return {"ok": True, "completed": completed, "screen": _parse_ui(d)}


def action_clear_text(d: u2.Device, params: dict) -> dict:
    """
    Clear the focused field, or tap a field by label first then clear it.
        {"action":"clear_text"}
        {"action":"clear_text","field":"Email"}
    """
    field = params.get("field")
    if field:
        err = _focus_field(d, field)
        if err:
            return err
    d.clear_text()
    wait_idle(d)
    return {"ok": True, "cleared": field or "focused field", "screen": _parse_ui(d)}


def action_swipe(d: u2.Device, params: dict) -> dict:
    direction = params.get("direction", "up")
    info = d.info
    w, h = info["displayWidth"], info["displayHeight"]
    cx = w // 2

    coords = {
        "up":    (cx, int(h * 0.75), cx, int(h * 0.25)),
        "down":  (cx, int(h * 0.25), cx, int(h * 0.75)),
        "left":  (int(w * 0.85), h // 2, int(w * 0.15), h // 2),
        "right": (int(w * 0.15), h // 2, int(w * 0.85), h // 2),
    }
    if direction not in coords:
        return {"ok": False, "error": f"Unknown direction '{direction}'. Use: up, down, left, right"}

    d.swipe(*coords[direction], duration=0.3)
    wait_idle(d)
    return {"ok": True, "swiped": direction, "screen": _parse_ui(d)}


def action_drag(d: u2.Device, params: dict) -> dict:
    """
    Single-point drag from one coordinate to another (press, move, release).
    Useful for sliders, reorderable list items, draggable map pins, etc. —
    anything that's a one-finger press-and-move rather than a quick swipe.

    Usage:
        {"action":"drag","start":[200,800],"end":[200,400]}
        {"action":"drag","start":[200,800],"end":[200,400],"duration":0.8}
    """
    start = params.get("start")
    end   = params.get("end")
    duration = float(params.get("duration", 0.5))

    if not start or not end:
        return {"ok": False, "error": "drag requires 'start' and 'end' coordinate pairs"}

    sx, sy = start
    ex, ey = end
    d.drag(sx, sy, ex, ey, duration=duration)
    wait_idle(d)
    return {"ok": True, "dragged": {"start": [sx, sy], "end": [ex, ey]}, "screen": _parse_ui(d)}


def action_pinch(d: u2.Device, params: dict) -> dict:
    """
    Two-finger pinch gesture for zooming — e.g. zooming a map in/out or
    zooming an image viewer. Built on uiautomator2's `d.gesture()`, which
    drives two touch points independently.

    Usage:
        {"action":"pinch","direction":"out","percent":80,"steps":50}   ← spread fingers apart (zoom in)
        {"action":"pinch","direction":"in","percent":80,"steps":50}    ← bring fingers together (zoom out)
        {"action":"pinch","direction":"out","center":[540,1200],"percent":50}

    `percent` (1-100, default 60) controls how much of the screen's shorter
    dimension the gesture spans — larger values mean a bigger, more
    deliberate pinch. `center` defaults to the screen center; override it
    to pinch around a specific point (e.g. a map marker). `steps` controls
    gesture smoothness/speed (more steps = slower, smoother).
    """
    direction = params.get("direction", "out")
    if direction not in ("in", "out"):
        return {"ok": False, "error": "pinch requires 'direction' to be 'in' or 'out'"}

    percent = max(1, min(100, float(params.get("percent", 60))))
    steps   = int(params.get("steps", 50))

    info = d.info
    w, h = info["displayWidth"], info["displayHeight"]
    cx, cy = params.get("center", [w // 2, h // 2])

    max_radius   = (min(w, h) / 2) * (percent / 100)
    inner_radius = max_radius * 0.1

    p1_far,  p2_far  = (cx - max_radius, cy), (cx + max_radius, cy)
    p1_near, p2_near = (cx - inner_radius, cy), (cx + inner_radius, cy)

    if direction == "out":   # fingers start close, end far apart — zoom in
        start1, start2, end1, end2 = p1_near, p2_near, p1_far, p2_far
    else:                    # fingers start far apart, end close — zoom out
        start1, start2, end1, end2 = p1_far, p2_far, p1_near, p2_near

    try:
        d.gesture(start1, start2, end1, end2, steps=steps)
    except Exception as e:
        return {"ok": False, "error": str(e)}

    wait_idle(d)
    return {
        "ok": True,
        "pinched": direction,
        "center": [cx, cy],
        "percent": percent,
        "screen": _parse_ui(d),
    }


def action_press_key(d: u2.Device, params: dict) -> dict:
    key_map = {
        "back":   "back",
        "home":   "home",
        "recent": "recent",
        "enter":  "enter",
    }
    key = params.get("key", "")
    if key not in key_map:
        return {"ok": False, "error": f"Unknown key '{key}'. Use: {list(key_map)}"}

    d.press(key_map[key])
    wait_idle(d)
    return {"ok": True, "pressed": key, "screen": _parse_ui(d)}


def action_wait_for(d: u2.Device, params: dict) -> dict:
    """
    Wait until a specific element appears on screen. Useful after triggering
    a slow transition (navigation, network load) when you know what element
    will confirm the new screen is ready.
    """
    label   = params.get("text", "")
    timeout = float(params.get("timeout", DEFAULT_ELEMENT_TIMEOUT))

    if not label:
        return {"ok": False, "error": "wait_for requires 'text'"}

    el = d(text=label)
    appeared = el.wait(timeout=timeout)
    if not appeared:
        el = d(description=label)
        appeared = el.wait(timeout=timeout)

    if appeared:
        wait_idle(d)
        return {"ok": True, "found": label, "screen": _parse_ui(d)}
    else:
        return {"ok": False, "error": f"'{label}' did not appear within {timeout}s", "screen": _parse_ui(d)}


def action_screenshot(d: u2.Device, params: dict) -> dict:
    path = params.get("path", "/tmp/screen.png")
    d.screenshot(path)
    return {"ok": True, "path": path}


def action_dump_ui(d: u2.Device, params: dict) -> dict:
    wait_idle(d, timeout=2)
    return {"ok": True, "screen": _parse_ui(d)}


def action_tap_selector(d: u2.Device, params: dict) -> dict:
    """
    Tap an element by structured UiSelector fields. Use when an element is
    not visible in the text-based dump (SVG, canvas, custom views).

    Usage:
        {"action":"tap_selector","className":"com.example.svg.CircleView","instance":2}
        {"action":"tap_selector","resourceId":"com.example.app:id/btn_photo"}
        {"action":"tap_selector","className":"android.widget.ImageButton","description":"Take photo"}

    Supported fields: className, resourceId, text, description, instance, index,
                       packageName, clickable, enabled — any uiautomator2 Selector kwarg.
    """
    selector_kwargs = {k: v for k, v in params.items()}

    if not selector_kwargs:
        return {"ok": False, "error": "tap_selector requires at least one selector field"}

    try:
        el = d(**selector_kwargs)
        if not el.exists(timeout=5):
            return {"ok": False, "error": f"No element found for selector: {selector_kwargs}"}

        info   = el.info
        bounds = info.get("bounds", {})
        cx = (bounds["left"] + bounds["right"])  // 2
        cy = (bounds["top"]  + bounds["bottom"]) // 2
        d.click(cx, cy)
        wait_idle(d)
        return {"ok": True, "selector": selector_kwargs, "coords": [cx, cy], "screen": _parse_ui(d)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def action_screen_on(d: u2.Device, params: dict) -> dict:
    """Explicitly wake the screen. Useful before a sequence of actions."""
    woke = ensure_screen_on(d)
    return {"ok": True, "woke_screen": woke, "screen": _parse_ui(d)}


def action_reset_app(d: u2.Device, params: dict) -> dict:
    """
    Clear all app data (cache, auth tokens, preferences) and relaunch.
    Equivalent to uninstalling and reinstalling — lands on the app's
    first-run/landing screen.

    Usage:
        {"action":"reset_app","package":"com.example.app"}
        {"action":"reset_app","package":"com.example.app","landmark_text":"Welcome"}

    If `landmark_text` is given, this waits (up to 15s) for that text to
    appear before returning, and reports ok=false if it never does — useful
    as a post-condition check for tests. Without it, this just clears data,
    relaunches, and returns the resulting screen for the caller to inspect.
    """
    package       = params.get("package")
    landmark_text = params.get("landmark_text")

    if not package:
        return {"ok": False, "error": "reset_app requires 'package'"}

    try:
        d.app_clear(package)          # pm clear — stops app and wipes data
        time.sleep(1)
        d.app_start(package)          # cold launch

        if landmark_text:
            el = d(text=landmark_text)
            appeared = el.wait(timeout=15)
            wait_idle(d)
            if not appeared:
                return {
                    "ok": False,
                    "error": f"App launched but landmark '{landmark_text}' not found after reset",
                    "screen": _parse_ui(d),
                }
        else:
            wait_idle(d)

        return {"ok": True, "package": package, "screen": _parse_ui(d)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def action_uninstall_app(d: u2.Device, params: dict) -> dict:
    """
    Fully uninstall the app from the device — not just clear its data
    (see reset_app for that).

    Usage:
        {"action":"uninstall_app","package":"com.example.app"}
    """
    package = params.get("package")
    if not package:
        return {"ok": False, "error": "uninstall_app requires 'package'"}
    try:
        success = d.app_uninstall(package)
        return {"ok": bool(success), "package": package, "uninstalled": bool(success)}
    except Exception as e:
        return {"ok": False, "error": str(e), "package": package}


def _dismiss_install_dialog(d: u2.Device, max_rounds: int = 3, settle: float = 1.0) -> list:
    """
    Best-effort dismissal of any on-device install confirmation dialog that
    can appear after `adb install` on some OEM skins (e.g. MIUI) even though
    ADB normally bypasses this. Each round does a single dump_hierarchy()
    call (not one per candidate label) and taps the first known button found.

    Deliberately does NOT tap 'Open' — relaunching, if wanted, is handled
    separately by the caller, so behavior stays deterministic regardless of
    whether this dialog appears at all.

    Returns the list of button labels actually tapped, in order — empty if
    no dialog was found in any round.
    """
    CANDIDATE_BUTTONS = [
        "INSTALL", "Install", "Install anyway", "INSTALL ANYWAY",
        "Continue", "OK", "DONE", "Done",
    ]
    tapped = []
    for _ in range(max_rounds):
        try:
            xml = d.dump_hierarchy()
            root = ET.fromstring(xml)
        except Exception:
            break

        match = None
        for node in root.iter():
            text  = node.attrib.get("text", "").strip()
            desc  = node.attrib.get("content-desc", "").strip()
            label = text or desc
            if label in CANDIDATE_BUTTONS and node.attrib.get("clickable") == "true":
                match = (label, node)
                break

        if match is None:
            break

        label, node = match
        center = _bounds_center(node.attrib.get("bounds", ""))
        if not center:
            break
        d.click(*center)
        tapped.append(label)
        time.sleep(settle)

    return tapped


def action_install_app(d: u2.Device, params: dict) -> dict:
    """
    Install (or upgrade) an APK via `adb install -r`, polling the device's
    UI concurrently to dismiss any on-device install confirmation dialog
    while the blocking `adb install` call is still in flight. This matters
    because polling only AFTER the call returns is too late — ADB gives up
    first with something like INSTALL_FAILED_USER_RESTRICTED on OEM skins
    that show a confirmation dialog.

    Usage:
        {"action":"install_app","apk_path":"/path/to/app.apk"}
        {"action":"install_app","apk_path":"...","package":"com.example.app","launch":true}
        {"action":"install_app","apk_path":"...","reinstall_first":true,"package":"com.example.app"}

    `reinstall_first` uninstalls `package` before installing — use this
    when switching between two builds signed with different keys, where a
    plain `adb install -r` would fail with a signature mismatch.
    `launch`, if true, starts `package` after a successful install and
    waits briefly for the UI to settle before returning the screen dump.
    """
    apk_path        = params.get("apk_path")
    package         = params.get("package")
    launch          = params.get("launch", False)
    reinstall_first = params.get("reinstall_first", False)
    timeout_s       = float(params.get("timeout", DEFAULT_INSTALL_TIMEOUT))

    if not apk_path:
        return {"ok": False, "error": "install_app requires 'apk_path'"}
    if reinstall_first and not package:
        return {"ok": False, "error": "reinstall_first requires 'package'"}

    uninstalled = None
    if reinstall_first:
        try:
            uninstalled = d.app_uninstall(package)
        except Exception as e:
            return {"ok": False, "error": f"Uninstall failed: {e}"}

    try:
        proc = subprocess.Popen(
            ["adb", "install", "-r", apk_path],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
    except Exception as e:
        return {"ok": False, "error": str(e)}

    start         = time.time()
    dismissed     = []
    timed_out     = False
    POLL_INTERVAL = 1.0

    while True:
        if proc.poll() is not None:
            break
        if time.time() - start > timeout_s:
            proc.kill()
            timed_out = True
            break
        tapped = _dismiss_install_dialog(d, max_rounds=1, settle=0.3)
        if tapped:
            dismissed.extend(tapped)
        time.sleep(POLL_INTERVAL)

    if timed_out:
        return {
            "ok": False,
            "error": f"adb install timed out after {timeout_s}s",
            "dismissedDialog": dismissed,
        }

    output     = proc.stdout.read() or ""
    returncode = proc.returncode
    success    = returncode == 0 and "Success" in output

    response = {
        "ok":         success,
        "apk_path":   apk_path,
        "returncode": returncode,
        "output":     output[-2000:],
    }
    if reinstall_first:
        response["uninstalledFirst"] = bool(uninstalled)
    if dismissed:
        response["dismissedDialog"] = dismissed

    if not success:
        return response

    # One more sweep in case the dialog appears slightly after `adb
    # install` returns rather than strictly during it.
    trailing = _dismiss_install_dialog(d)
    if trailing:
        response.setdefault("dismissedDialog", [])
        response["dismissedDialog"].extend(trailing)

    if launch:
        if not package:
            response["launchError"] = "launch=true requires 'package'"
        else:
            try:
                d.app_start(package)
                wait_idle(d, timeout=3)
                response["screen"] = _parse_ui(d)
            except Exception as e:
                response["launchError"] = str(e)

    return response


def action_set_location(d: u2.Device, params: dict) -> dict:
    """
    Toggle a mock-location ("fake GPS") app to spoof the device's location,
    by driving its UI rather than writing location data directly via ADB.
    Direct ADB location injection tends to make apps that read from the
    Fused Location Provider flicker between the real and spoofed position;
    going through a dedicated mock-location app's own UI avoids that.

    This action is intentionally generic about *which* fake-GPS app is
    used — it operates purely by element text ("Start", "Stop", "OK",
    etc.), so it works with most simple mock-location apps as long as:
      1. The app is installed and selected as the mock-location app under
         Developer Options.
      2. `mock_app_package` is passed in (its main activity is launched
         via `am start`).
      3. The app exposes Start/Stop buttons and Latitude/Longitude input
         fields somewhere reachable by tapping `menu_coords` (see below).

    Because every fake-GPS app's UI layout differs, the exact tap sequence
    to reach the latitude/longitude fields is app-specific. This action
    covers the common "menu button → search/manual entry → lat/lon fields
    → OK → Start" shape; you will likely need to adjust `menu_coords` (and
    possibly the field/button labels) for whichever app you use — see the
    README for notes on adapting this to a specific mock-location app.

    Usage:
        {
          "action": "set_location",
          "lat": 51.919495, "lon": 4.475682,
          "mock_app_package": "com.example.fakegps",
          "return_to_package": "com.example.app",
          "menu_coords": [1024, 188]
        }
        {"action":"set_location","stop":true,"mock_app_package":"com.example.fakegps"}
    """
    mock_pkg   = params.get("mock_app_package")
    return_pkg = params.get("return_to_package")
    menu_coords = params.get("menu_coords")

    if not mock_pkg:
        return {"ok": False, "error": "set_location requires 'mock_app_package'"}

    def launch_mock_app():
        subprocess.run([
            "adb", "shell", "am", "start",
            "-n", f"{mock_pkg}/.MainActivity",
        ], timeout=5, capture_output=True)
        time.sleep(3)
        wait_idle(d)

    def return_to_app():
        if return_pkg:
            d.app_start(return_pkg)
            time.sleep(2)
            wait_idle(d)

    if params.get("stop"):
        try:
            launch_mock_app()
            stop_node = _find_element(d, "Stop")
            if stop_node is not None:
                center = _bounds_center(stop_node.attrib.get("bounds", ""))
                if center:
                    d.click(*center)
                    time.sleep(1)
                    wait_idle(d)
            return_to_app()
            return {"ok": True, "stopped": True, "screen": _parse_ui(d)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    lat = params.get("lat")
    lon = params.get("lon")
    if lat is None or lon is None:
        return {"ok": False, "error": "set_location requires 'lat' and 'lon'"}

    try:
        launch_mock_app()

        # Stop any active spoofing first — otherwise coordinates won't update.
        stop_node = _find_element(d, "Stop")
        if stop_node is not None:
            center = _bounds_center(stop_node.attrib.get("bounds", ""))
            if center:
                d.click(*center)
                time.sleep(1)
                wait_idle(d)

        if menu_coords:
            d.click(*menu_coords)
            time.sleep(1)
            wait_idle(d)

        search = d(text="Search")
        if search.exists(timeout=5):
            search.click()
            time.sleep(1)
            wait_idle(d)

        lat_field = _find_element(d, "Latitude")
        if lat_field is None:
            return {"ok": False, "error": "Could not find Latitude field", "screen": _parse_ui(d)}
        center = _bounds_center(lat_field.attrib.get("bounds", ""))
        if not center:
            return {"ok": False, "error": "Could not parse Latitude bounds"}
        d.click(*center)
        time.sleep(0.5)
        d.clear_text()
        d.send_keys(str(lat))
        time.sleep(0.5)

        lon_field = _find_element(d, "Longitude")
        if lon_field is None:
            return {"ok": False, "error": "Could not find Longitude field", "screen": _parse_ui(d)}
        center = _bounds_center(lon_field.attrib.get("bounds", ""))
        if not center:
            return {"ok": False, "error": "Could not parse Longitude bounds"}
        d.click(*center)
        time.sleep(0.5)
        d.clear_text()
        d.send_keys(str(lon))
        time.sleep(1.5)

        ok_node = _find_element(d, "OK")
        if ok_node is None:
            return {"ok": False, "error": "Could not find OK button", "screen": _parse_ui(d)}
        center = _bounds_center(ok_node.attrib.get("bounds", ""))
        if not center:
            return {"ok": False, "error": "Could not parse OK bounds"}
        d.click(*center)
        time.sleep(2)
        wait_idle(d)

        # Starting the mock-location service is not instant — the toolbar
        # (Start/Stop buttons) can disappear from the dump entirely for a
        # few seconds while it spins up, before settling with Stop enabled.
        # Poll for that real signal rather than a fixed sleep, and retry
        # the tap once if it doesn't happen.
        start_node = _find_element(d, "Start")
        if start_node is None:
            return {"ok": False, "error": "Could not find Start button", "screen": _parse_ui(d)}
        center = _bounds_center(start_node.attrib.get("bounds", ""))
        if not center:
            return {"ok": False, "error": "Could not parse Start bounds", "screen": _parse_ui(d)}
        d.click(*center)

        started = _wait_for_enabled(d, "Stop", timeout=8.0)
        if not started:
            retry_node = _find_element(d, "Start")
            if retry_node is not None:
                retry_center = _bounds_center(retry_node.attrib.get("bounds", ""))
                if retry_center:
                    d.click(*retry_center)
                    started = _wait_for_enabled(d, "Stop", timeout=8.0)

        if not started:
            return {
                "ok": False,
                "error": "Tapped 'Start' but location spoofing never toggled on (Stop button never became enabled)",
                "screen": _parse_ui(d),
            }

        return_to_app()

        return {
            "ok": True,
            "location": {"lat": lat, "lon": lon},
            "screen": _parse_ui(d),
        }

    except Exception as e:
        return {"ok": False, "error": str(e)}


# ── environment diagnostics ────────────────────────────────────────────────────
def _check_python() -> dict:
    ok = sys.version_info >= (3, 8)
    return {
        "name": "python",
        "ok": ok,
        "detail": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "fix": "Install Python 3.8+ from https://www.python.org/downloads/" if not ok else None,
    }


def _check_uiautomator2_installed() -> dict:
    try:
        import uiautomator2  # noqa: F401
        return {"name": "uiautomator2 package", "ok": True, "detail": "installed", "fix": None}
    except ImportError:
        return {
            "name": "uiautomator2 package",
            "ok": False,
            "detail": "not installed",
            "fix": "pip install uiautomator2",
        }


def _check_adb_on_path() -> dict:
    try:
        out = subprocess.run(["adb", "version"], capture_output=True, text=True, timeout=5)
        first_line = out.stdout.splitlines()[0] if out.stdout else "adb found"
        return {"name": "adb on PATH", "ok": out.returncode == 0, "detail": first_line, "fix": None}
    except FileNotFoundError:
        return {
            "name": "adb on PATH",
            "ok": False,
            "detail": "not found",
            "fix": (
                "Install Android platform-tools (no Android Studio needed):\n"
                "    macOS:   brew install android-platform-tools\n"
                "    Linux:   sudo apt install android-tools-adb   (or download platform-tools zip)\n"
                "    Windows: download platform-tools zip from "
                "https://developer.android.com/tools/releases/platform-tools and add it to PATH"
            ),
        }
    except Exception as e:
        return {"name": "adb on PATH", "ok": False, "detail": str(e), "fix": "Reinstall platform-tools"}


def _check_device_connected() -> dict:
    try:
        out = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=5)
        lines = [line for line in out.stdout.splitlines()[1:] if line.strip()]
        devices = [line.split("\t") for line in lines]
        online = [d for d in devices if len(d) == 2 and d[1] == "device"]
        unauthorized = [d for d in devices if len(d) == 2 and d[1] == "unauthorized"]

        if online:
            return {"name": "device connected", "ok": True, "detail": online[0][0], "fix": None}
        if unauthorized:
            return {
                "name": "device connected",
                "ok": False,
                "detail": f"unauthorized: {unauthorized[0][0]}",
                "fix": "Check the phone screen for an 'Allow USB debugging?' prompt and tap Allow",
            }
        return {
            "name": "device connected",
            "ok": False,
            "detail": "no devices found",
            "fix": (
                "1. Enable Developer Options: Settings > About phone > tap 'Build number' 7 times\n"
                "    2. Enable USB debugging: Settings > Developer options > USB debugging\n"
                "    3. Connect the phone by USB (or run 'adb connect <ip>:5555' for Wi-Fi) "
                "and accept the prompt on the device"
            ),
        }
    except FileNotFoundError:
        return {"name": "device connected", "ok": False, "detail": "adb not found", "fix": "Install adb first"}
    except Exception as e:
        return {"name": "device connected", "ok": False, "detail": str(e), "fix": None}


def _check_agent_reachable() -> dict:
    try:
        d = u2.connect()
        info = d.info
        return {
            "name": "uiautomator2 agent",
            "ok": True,
            "detail": f"connected, {info.get('displayWidth')}x{info.get('displayHeight')}",
            "fix": None,
        }
    except Exception as e:
        return {
            "name": "uiautomator2 agent",
            "ok": False,
            "detail": str(e),
            "fix": "Run 'tapium setup' to (re)install the on-device agent, or 'python -m uiautomator2 init'",
        }


def run_doctor(verbose: bool = True) -> dict:
    """
    Run all environment checks in order and report pass/fail per step.
    Later checks are skipped if an earlier hard-blocking one fails, since
    they'd fail for the same root cause and just add noise.
    """
    checks = []

    checks.append(_check_python())
    checks.append(_check_uiautomator2_installed())
    checks.append(_check_adb_on_path())

    if checks[-1]["ok"]:
        checks.append(_check_device_connected())
        if checks[-1]["ok"] and checks[1]["ok"]:
            checks.append(_check_agent_reachable())

    all_ok = all(c["ok"] for c in checks)

    if verbose:
        print("tapium doctor\n")
        for c in checks:
            mark = "✅" if c["ok"] else "❌"
            print(f"{mark} {c['name']}: {c['detail']}")
            if not c["ok"] and c["fix"]:
                print(f"   → {c['fix']}")
        print()
        print("All checks passed — ready to go." if all_ok else "Some checks failed — see fixes above.")

    return {"ok": all_ok, "checks": checks}


def run_setup() -> dict:
    """
    Best-effort one-shot setup: checks prerequisites, and if adb + a device
    are present but the on-device agent isn't reachable, runs
    `uiautomator2 init` to install/refresh it. Does not attempt to install
    Python or adb itself — those require OS-level package managers or a
    manual download, so `doctor`'s fix hints are printed instead.
    """
    print("tapium setup\n")
    result = run_doctor(verbose=True)

    checks_by_name = {c["name"]: c for c in result["checks"]}
    adb_ok = checks_by_name.get("adb on PATH", {}).get("ok")
    device_ok = checks_by_name.get("device connected", {}).get("ok")
    agent_ok = checks_by_name.get("uiautomator2 agent", {}).get("ok")

    if adb_ok and device_ok and not agent_ok:
        print("\nInstalling the on-device uiautomator2 agent (uiautomator2 init)...\n")
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "uiautomator2", "init"],
                timeout=120,
            )
            if proc.returncode == 0:
                print("\nAgent installed. Re-checking...\n")
                return run_doctor(verbose=True)
            else:
                print(f"\n'uiautomator2 init' exited with code {proc.returncode}. See output above.")
        except Exception as e:
            print(f"\nCould not run 'uiautomator2 init': {e}")

    if not (adb_ok and device_ok):
        print("\nFix the ❌ items above, then run 'tapium setup' again.")

    return result


# ── dispatcher ────────────────────────────────────────────────────────────────
ACTIONS = {
    "tap":            action_tap,
    "input_text":     action_input_text,
    "input_sequence": action_input_sequence,
    "clear_text":     action_clear_text,
    "swipe":          action_swipe,
    "drag":           action_drag,
    "pinch":          action_pinch,
    "press_key":      action_press_key,
    "wait_for":       action_wait_for,
    "screenshot":     action_screenshot,
    "dump_ui":        action_dump_ui,
    "screen_on":      action_screen_on,
    "reset_app":      action_reset_app,
    "uninstall_app":  action_uninstall_app,
    "install_app":    action_install_app,
    "tap_selector":   action_tap_selector,
    "set_location":   action_set_location,
}


def main() -> None:
    if len(sys.argv) < 2:
        print(json.dumps({
            "ok": False,
            "error": "No action provided. Pass a JSON string as the first argument.",
            "example": 'python tapium.py \'{"action":"dump_ui"}\'',
        }))
        sys.exit(1)

    # Non-JSON subcommands — plain CLI, human-readable output, not JSON-in/out.
    if sys.argv[1] == "doctor":
        result = run_doctor(verbose=True)
        sys.exit(0 if result["ok"] else 1)

    if sys.argv[1] == "setup":
        result = run_setup()
        sys.exit(0 if result["ok"] else 1)

    try:
        params = json.loads(sys.argv[1])
    except json.JSONDecodeError as e:
        print(json.dumps({"ok": False, "error": f"Invalid JSON: {e}"}))
        sys.exit(1)

    action = params.pop("action", None)
    if action not in ACTIONS:
        print(json.dumps({
            "ok": False,
            "error": f"Unknown action '{action}'",
            "available": list(ACTIONS.keys()),
        }))
        sys.exit(1)

    try:
        d = connect()
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"Could not connect to device: {e}"}))
        sys.exit(1)

    result = ACTIONS[action](d, params)
    print(json.dumps(result))
    sys.exit(0 if result.get("ok") else 1)


if __name__ == "__main__":
    main()
