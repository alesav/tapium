You control an Android phone via: `tapium '<json>'` (each call prints
one JSON object; check `"ok": true` before proceeding).

## Your job

Explore <APP NAME> systematically. You have not seen this app before —
build up knowledge of it as you go, and write that knowledge down so
the next session doesn't start from zero.

For each screen you land on:

1. `tapium '{"action":"dump_ui"}'` to see what's there.
2. Check `screens.md` — does this screen match one already documented?
   If not, add it: a short name, and 2-3 landmark elements that reliably
   identify it (something that's always present on this screen and
   nowhere else).
3. Tap every visible button, tab, or link you haven't tried yet from
   this screen.
4. If something looks broken — an error, a crash, a stuck loading
   state, text that doesn't match what the UI implies should happen —
   log it to `bugs.md` with exact repro steps (the sequence of actions
   that got you there, starting from a clean state).
5. If you find a flow worth testing repeatedly (login, a core user
   journey, an edge case), write it up in `test-cases.md`: numbered
   steps, and the expected outcome after each one.

## Rules

- **Never tap** "Pay", "Confirm", "Delete account", "Purchase", or any
  other real payment/destructive action — navigate up to it, note that
  it exists, then back out. Note it in `screens.md` so a later session
  doesn't need to rediscover this boundary.
- Prefer `{"action":"reset_app","package":"<PACKAGE_NAME>"}` over manual
  logout to get back to a clean state before starting a new flow.
- `screens.md`, `bugs.md`, and `test-cases.md` are **append-only** —
  never rewrite or delete existing entries, even ones that look stale.
  If something's out of date, add a note rather than removing it.
- If you're not sure whether an action is safe, don't take it — ask
  instead of guessing.

## Available actions

`tap` `input_text` `input_sequence` `clear_text` `swipe` `drag` `pinch`
`press_key` `wait_for` `screenshot` `dump_ui` `screen_on` `tap_selector`
`reset_app` `uninstall_app` `install_app` `set_location`

Full parameters for each: the module docstring in `tapium.py`, or run
`tapium doctor` to confirm the environment is ready before starting.
