# Changelog

All notable changes to this project are documented here.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added
- Initial public release as **Tapium**.
- `tapium.py` — single-file, JSON-in/JSON-out Android device controller
  built on `uiautomator2`: `tap`, `input_text`, `input_sequence`,
  `clear_text`, `swipe`, `drag`, `pinch`, `press_key`, `wait_for`,
  `screenshot`, `dump_ui`, `screen_on`, `tap_selector`, `reset_app`,
  `uninstall_app`, `install_app`, `set_location`.
- `api.py` — example backend-API client showing the pattern for pairing
  `tapium.py` with a backend for agent-driven test setup/verification
  (fully mocked out of the box, no real backend required).
- Test suite (`tests/`) covering the pure parsing/selection logic and a
  representative slice of actions against a fake in-memory device — no
  real Android device needed to run it.
- GitHub Actions CI (lint + compile check + tests across Python 3.10–3.12).
- `CONTRIBUTING.md`, issue templates, PR template.
