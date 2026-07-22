# Tapium

[![CI](https://github.com/alesav/tapium/actions/workflows/ci.yml/badge.svg)](https://github.com/alesav/tapium/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A single-file, AI-agent-friendly controller for driving a real Android
device (or emulator) over USB/ADB — built for letting an LLM agent (or
any script) operate an app the way a human tester would: read the screen,
tap things, type things, wait for things to load.

Built on top of [`uiautomator2`](https://github.com/openatx/uiautomator2).

**New here?** [USE_CASES.md](USE_CASES.md) walks through two full,
worked examples — automating a repetitive app flow, and using an agent
for exploratory QA testing and regression suites — before you write any
code of your own.

## Why

Most UI-automation tooling is built for deterministic test scripts: you
know in advance exactly which element you want, and you write a selector
for it. Driving a device from an LLM agent is different — the agent needs
to *see* the screen as structured data, decide what to do, act, and see
the result, in a tight loop, with minimal round-trips.

`tapium.py` is a thin JSON-in/JSON-out CLI wrapping `uiautomator2` with
that loop in mind:

- Every action returns a compact list of on-screen elements (text,
  content-description, bounds, clickable/scrollable flags) — enough for
  an agent to decide its next move without a screenshot.
- Every mutating action waits for the UI to settle before returning, so
  the response already reflects the new screen — no extra "dump" call
  needed in the common case.
- Actions are addressed by visible text/description first, with explicit
  coordinate and structured-selector fallbacks for elements that don't
  expose text (SVGs, canvases, custom views).

## Install

```bash
pip install tapium
tapium setup
```

`tapium setup` checks Python, `adb`, and a connected device, tells you
exactly how to install anything missing (no Android Studio — just the
~10MB platform-tools binary), and installs the on-device automation agent.
Run `tapium doctor` any time afterward to re-check the environment without
reinstalling anything.

Full first-run walkthrough, including enabling USB debugging on the phone:
see [AGENTS.md](AGENTS.md).

Requires:
- A device with USB debugging enabled, connected and authorized (`adb devices` should list it)
- Python 3.8+

Installing from this repo instead of PyPI: `pip install -e .`, or the
older `pip install -r requirements.txt` + running `tapium.py` directly
still works identically.

## Usage

```bash
tapium '{"action":"dump_ui"}'
tapium '{"action":"tap","text":"Sign in"}'
tapium '{"action":"input_text","field":"Email","text":"hello@example.com"}'
tapium '{"action":"swipe","direction":"up"}'
tapium '{"action":"wait_for","text":"Welcome back","timeout":15}'
```

(Running from source instead of the installed command: swap `tapium` for
`python tapium.py` in the examples above.)

Every call prints one JSON object to stdout and exits `0` on success
(`"ok": true`) or `1` on failure (`"ok": false, "error": "..."`).

See the module docstring in `tapium.py` for the full action reference,
`examples/` for a worked example of wiring this into an agent loop, and
[USE_CASES.md](USE_CASES.md) for two complete real-world patterns.

## Pairing with a backend API

`api.py` shows the intended pattern for combining `tapium.py` with a
backend API client in agent-driven testing — using the API for setup/
verification that's slow or flaky to reach purely through the UI (seed an
account, check a record landed, tear down test data), while
`tapium.py` drives the app itself.

**Every request in `api.py` is mocked** — there's no real backend wired
up, just an in-memory store and canned responses, so you can run it
out of the box and see the shape of the integration:

```bash
python3 api.py '{"command":"get_user","id":"user_123","env":"staging"}'
python3 api.py '{"command":"create_user","email":"demo@example.com","env":"staging"}'
python3 api.py '{"command":"list_orders","user_id":"user_123","env":"staging"}'
```

To point this at a real API: replace `_mock_request()` with actual HTTP
calls (e.g. via `requests`) against `env["base_url"]`, authenticated with
`env["token"]`. Copy `environments.example.json` to `environments.json`
and fill in real tokens — that file is gitignored so secrets never get
committed.

## Design notes

- **No app-specific defaults.** Package names, landmark screen text, and
  APK paths are always passed in by the caller — this tool knows nothing
  about any particular app.
- **Text/description first, coordinates as fallback.** Tapping by visible
  label is far more robust to minor layout shifts than fixed coordinates,
  but `tap` and `input_sequence` both support coordinate fallbacks for the
  cases where an element genuinely has no usable label.
- **`tap_selector` for non-text elements.** SVG/canvas/custom-rendered UI
  often has no `text` or `content-desc` at all — `tap_selector` exposes
  the underlying uiautomator2 `Selector` kwargs (`className`, `instance`,
  `resourceId`, etc.) for those cases.
- **`set_location` is necessarily a bit app-specific.** Mock-location apps
  all have different UIs, so this action drives a fairly common
  "menu → search → lat/lon fields → OK → Start" shape and exposes the
  parts likely to need adjusting (`menu_coords`, package names) as
  arguments rather than hardcoding them. You may need to adapt the field
  labels for whichever mock-location app you use — see the docstring.

## What this is not

This isn't a full test framework — there's no assertion library, test
runner, or reporting built in. It's the device-control layer you'd build
one on top of. If you're looking for that, this plays well alongside
`pytest` (treat each action's `"ok"` field and `"screen"` contents as your
assertions) or an agent framework that can shell out and parse JSON.

## Testing

The test suite runs against a fake in-memory device — **no real Android
device or emulator required**:

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full development workflow.

## Contributing

Issues and PRs welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT — see [LICENSE](LICENSE).
