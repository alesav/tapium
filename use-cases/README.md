# Use Cases — Runnable Examples

Each subfolder here is a self-contained, runnable example built on
Tapium. They're not toy snippets — they're adapted from real scripts
that were actually run against real devices. See [../USE_CASES.md](../USE_CASES.md)
for the narrative write-up of why each pattern is useful; this folder
is the code.

## [`instagram-story-watcher/`](instagram-story-watcher/)

Read-only monitoring: scroll a followers list, detect which accounts
currently have an active story, log the result. No taps on any other
account's content beyond scrolling your own view — see that folder's
README for exactly where the line is drawn and why.

**Demonstrates:** parsing `dump_ui` output for app-specific UI structure,
scrolling to page through a list, building up written knowledge about an
app's element layout as you go.

## [`qa-exploratory/`](qa-exploratory/)

An agent prompt + project layout for exploratory testing: point an agent
at an app it's never seen, have it tap through systematically, and keep
three living documents (`screens.md`, `bugs.md`, `test-cases.md`) updated
as it goes. Includes a template for turning a documented flow into a
real `pytest` test.

**Demonstrates:** the "explore → document → automate" pipeline, and how
to keep an agent from re-discovering the same app from scratch every run.

## [`gps-spoofing/`](gps-spoofing/)

Testing location-dependent features by spoofing GPS via `set_location`,
paired with a mocked backend to independently verify what the app
*should* be showing for that location.

**Demonstrates:** `set_location` end to end, and the "drive the UI +
verify against a backend" pattern for cases where UI-only assertions
can't tell you if what's on screen is actually correct.

## Running these

All three assume you've already run `tapium setup` (see the main
[README](../README.md)) and have a device connected. Each subfolder's
own README has the exact commands — none of them need anything beyond
`pip install tapium` plus what's in that folder's `requirements.txt`
(if any).
