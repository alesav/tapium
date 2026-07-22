# Contributing to Tapium

Thanks for considering a contribution — issues, PRs, and questions are all welcome.

## Getting set up

```bash
git clone https://github.com/<your-fork>/tapium.git
cd tapium
pip install -r requirements-dev.txt
```

No Android device is required to run the test suite — every test drives
`tapium.py`'s logic against a fake in-memory device (see `tests/conftest.py`),
not a real one. You'll only need a real device/emulator connected via ADB
if you're manually testing a change against `python tapium.py '<json>'`
itself.

## Running the checks locally

```bash
ruff check .              # lint
python -m py_compile tapium.py api.py   # syntax/import check
pytest tests/ -v           # test suite
```

All three run in CI on every push and PR (see `.github/workflows/ci.yml`)
across Python 3.10–3.12 — please make sure they pass locally before opening
a PR.

## Making a change

- **Bug fixes / small improvements**: open a PR directly. Include a short
  description of what was broken (or could be better) and how your change
  fixes it.
- **New actions or larger changes**: please open an issue first to discuss
  the shape of the change before investing time in an implementation —
  this project deliberately stays a thin, single-file, dependency-light
  layer (see the README's "Design notes" and "What this is not"), so not
  every idea is a good fit, and it's better to align on that early.
- **Tests**: if you add a new action or change existing logic, add or
  update tests in `tests/`. Pure-logic pieces (parsing, bounds math,
  selection logic) should get direct unit tests; anything that only
  touches the device via `uiautomator2` calls can be tested against the
  `FakeDevice` fixture in `tests/conftest.py` the same way the existing
  action tests are.
- **Style**: match the existing code — plain functions, JSON-serializable
  dicts in and out, no app-specific defaults hardcoded into `tapium.py`
  (package names, screen text, etc. are always caller-supplied parameters).

## Reporting a bug

Please include:
- The exact JSON action you ran and the full JSON response you got back
- Android version / device or emulator model, if relevant
- What you expected to happen instead

## Code of conduct

Be respectful and constructive. Disagreements about design are fine and
expected — personal attacks, harassment, or bad-faith engagement are not.
