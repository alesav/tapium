# Test Cases

Flows worth testing repeatedly, found during exploration. **Append-only.**
Once a case here is worth automating, turn it into a pytest test — see
`test_login_example.py` in this folder for the shape to follow.

## Template for a new entry

```markdown
### TC-<number>: <short title>

- Preconditions: <clean state? logged in? specific env?>
- Steps:
  1. ...
  2. ...
- Expected result: <what should be true at the end>
- Automated: <yes, in tests/<path> | not yet>
```

## Example (delete once you have real entries)

### TC-001: Login — positive scenario

- Preconditions: app freshly reset (logged out), valid test credentials
- Steps:
  1. `reset_app` to land on Login Screen
  2. `input_sequence`: fill Email + Password, tap "Log in"
  3. `wait_for` the Home screen's landmark element (e.g. a "Home" title
     or bottom-nav tab)
- Expected result: Home screen loads within 15s, no error dialog
- Automated: yes, in `test_login_example.py`
