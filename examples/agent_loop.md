# Example: wiring tapium into an agent loop

A minimal system prompt you can give an LLM agent that can shell out to
`tapium.py`:

```
You control an Android phone via: python tapium.py '<json>'

Rules:
1. Start every NEW task with dump_ui to see the current screen.
2. After each action the response already includes the updated "screen"
   list — do NOT call dump_ui again unless you need to re-check without
   acting.
3. Use wait_for when you trigger something slow (loading screens, network).
4. Prefer tapping by "text" over "coords" — it's more robust to minor
   layout shifts.
5. All responses are JSON. Check "ok": false for errors before proceeding.

Actions: tap | input_text | input_sequence | clear_text | swipe | drag |
pinch | press_key | wait_for | screenshot | dump_ui | screen_on |
tap_selector | reset_app | uninstall_app | install_app | set_location
```

## Example: a simple login flow

```bash
python tapium.py '{"action":"dump_ui"}'

python tapium.py '{
  "action": "input_sequence",
  "steps": [
    {"field": "Email",    "text": "demo@example.com"},
    {"field": "Password", "text": "hunter2"},
    {"tap_text": "Sign in"}
  ]
}'

python tapium.py '{"action":"wait_for","text":"Home","timeout":15}'
```

## Example: scripted from Python instead of the CLI

You can also import the action functions directly rather than shelling out:

```python
from tapium import connect, action_tap, action_dump_ui

d = connect()
print(action_dump_ui(d, {}))
print(action_tap(d, {"text": "Sign in"}))
```
