# Bugs

Bug log from exploratory sessions. **Append-only** — never rewrite or
delete an entry, even a stale one (add a follow-up note instead).

## Template for a new entry

```markdown
### <short title>

- Found: <date>
- Screen: <where it happened, per screens.md naming>
- Repro steps (from a clean state):
  1. ...
  2. ...
- Expected: <what should have happened>
- Actual: <what happened instead>
- Severity: <blocker | major | minor | cosmetic>
```

## Example (delete once you have real entries)

### Password field accepts empty submit with no error

- Found: 2026-01-01
- Screen: Login Screen
- Repro steps (from a clean state):
  1. `reset_app` to land on Login Screen
  2. `{"action":"input_text","field":"Email","text":"test@example.com"}`
  3. Leave Password field empty
  4. `{"action":"tap","text":"Log in"}`
- Expected: inline validation error under the Password field
- Actual: button does nothing, no visible error, `dump_ui` shows no new
  elements — silent no-op
- Severity: minor
