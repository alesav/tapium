# Screens

Registry of every discovered screen, with the landmark elements that
reliably identify it. Check this before assuming a `dump_ui` result is
a new screen — it might already be documented.

**Append-only** — never rewrite or delete an entry.

## Template for a new entry

```markdown
### <Screen Name>

- Identified by: <element that's always present here and nowhere else>
- Key elements:
  - <element> — <what it does>
  - <element> — <what it does>
- Notes: <anything non-obvious — states this screen can be in, gotchas>
```

## Example (delete once you have real entries)

### Login Screen

- Identified by: `Log in` button + an `EditText` with hint "Email"
- Key elements:
  - Email field (`EditText`, hint: "Email")
  - Password field (`EditText`, hint: "Password")
  - `Log in` button
  - `Sign up` link — navigates to registration, not covered yet
- Notes: none yet
