# Tapium — Agent Instructions

This file tells an AI coding agent (or a human following along) how to get
Tapium working end-to-end: install Python, install Tapium, connect a real
Android phone, and start sending actions. No Android Studio required.

## 1. Prerequisites

- **Python 3.8+**
  - macOS: `brew install python` (or use the system Python 3 if `python3 --version` already shows 3.8+)
  - Linux: `sudo apt install python3 python3-pip`
  - Windows: install from https://www.python.org/downloads/ (check "Add to PATH" during install)
- **An Android phone** with a USB cable, or same-Wi-Fi network for wireless ADB.
  Android Studio is **not** needed at any point in this setup.

## 2. Install Tapium

```bash
pip install tapium
```

This pulls in `uiautomator2` automatically and installs a `tapium` command
on PATH. (If installing from this repo instead of PyPI: `pip install -e .`)

`adb` is a separate binary and is not installed by pip — step 3 covers it.

## 3. Enable USB debugging on the phone

1. Settings → About phone → tap "Build number" 7 times (enables Developer Options)
2. Settings → Developer options → turn on "USB debugging"
3. Connect the phone via USB and tap "Allow" on the "Allow USB debugging?" prompt

## 4. Run setup

```bash
tapium setup
```

This single command:
- Checks Python, `adb`, and the `uiautomator2` package
- Tells you exactly how to install `adb` if it's missing (no Android
  Studio — just the platform-tools binary, via `brew`, `apt`, or a small
  zip download depending on OS)
- Checks a device is connected and authorized
- Installs the on-device automation agent (`uiautomator2 init`) if needed
- Prints ✅/❌ for each step with a fix hint next to any ❌

Re-run `tapium setup` any time after fixing an item — it's idempotent.

## 5. Verify everything works

```bash
tapium doctor
```

Same checks as `setup`, without attempting any fixes — use this to
re-verify the environment mid-session (e.g. after a phone reboot or
reconnect) without re-running the install step.

## 6. Send actions

Every action is a single JSON argument; every response is a single JSON
object on stdout.

```bash
tapium '{"action":"dump_ui"}'
tapium '{"action":"tap","text":"Sign in"}'
tapium '{"action":"input_text","field":"Email","text":"hello@example.com"}'
```

Exit code is `0` when `"ok": true`, `1` when `"ok": false` — safe to check
in a script or agent loop without parsing JSON just to know success/failure.

Full action reference: see the module docstring in `tapium.py`, or the
`README.md` in this repo.

## Troubleshooting quick reference

| Symptom | Fix |
|---|---|
| `adb: command not found` | `tapium setup` prints the OS-specific install command |
| `tapium doctor` shows "no devices found" | Re-check USB debugging is enabled and the cable supports data (not charge-only) |
| Device shows "unauthorized" | Look at the phone screen for the debugging prompt and tap Allow |
| `uiautomator2 agent` check fails after device connects | Run `tapium setup` again — it re-runs `uiautomator2 init` |
