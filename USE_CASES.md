# Use Cases

Tapium is a low-level building block — a JSON-in/JSON-out way to see and
control an Android screen. On its own that's not obviously useful; it
becomes useful once you put an agent (or a script) in the loop that reads
the screen, decides what to do, and acts. This page walks through two real
patterns, end to end, so you can see what "useful" looks like before you've
built anything yourself.

## 1. Automating a repetitive app flow

**The idea:** any flow you'd otherwise do by hand on your phone — check
something, react to it, log it — can be scripted once the screen is
readable as structured JSON instead of pixels.

**Concrete example:** a personal Instagram bot that watches a specific
account's followers list and reports which ones currently have an active
story, without opening the app yourself. The flow:

```bash
# 1. Open the followers list, dump the screen
tapium '{"action":"dump_ui"}'

# 2. Each follower row's avatar container has two children when a story
#    is active (a ring-drawable View + the ImageView), one child when not.
#    Parse that from the dump_ui output client-side — no special action
#    needed, this is just reading the JSON tapium already returned.

# 3. Tap a row that has an active story to open it
tapium '{"action":"tap","coords":[135,650]}'

# 4. Give the story player a moment to load, then read who it is
tapium '{"action":"wait_for","text":"18 hours ago","timeout":5}'
tapium '{"action":"dump_ui"}'

# 5. Back out to the followers list and move to the next row
tapium '{"action":"press_key","key":"back"}'
```

Wrap that loop in a small Python script (or an agent given the action
reference) and you have a "check for new stories" job you can run on a
schedule — the kind of thing that's normally either manual or requires a
full test-automation framework to script.

**Where the real logic lives:** figuring out *which* elements matter for a
given app is inherently app-specific — resource-ids, content-desc labels,
and layout structure differ from app to app and even version to version.
Tapium doesn't try to know this in advance (see "No app-specific defaults"
in the main README); you (or an agent doing the exploring) build up that
knowledge once, write it down, and reuse it. Worth keeping a short
markdown file alongside your script — screen names, key elements, quirks
— exactly like `instructions.md` in the use case above. It becomes the
reference an agent reads before touching the device, so it doesn't
rediscover the same UI from scratch every run.

> **A note on where automation stops being okay.** Reading a screen and
> reacting to it (checking, monitoring, notifying) is a very different
> thing from repeatedly performing actions that count as engagement on a
> platform you don't control — likes, follows, comments, DMs. Most
> platforms' terms of service explicitly prohibit automated engagement,
> and it risks the account being flagged or banned regardless of how
> "human-like" the timing is. If you're automating against a third-party
> app, automate observation and your own account's actions — not
> interactions with other people's content. When in doubt, write it down
> as reference documentation for manual use rather than a script that
> runs unattended.

## 2. QA — exploratory testing and regression suites

**The idea:** point an agent at your app with a JSON action reference and
some project conventions, and it can do two different jobs:

- **Exploratory testing** — tap through the app it's never seen, keep
  notes on what it finds, and write up test cases as it goes.
- **Turn a written-up flow into an automated test** — once a flow is
  documented, ask the agent to translate it into a runnable test script.

**Exploratory testing, step by step:**

```bash
# Start of every session — see what screen we're actually on
tapium '{"action":"dump_ui"}'
```

Give the agent a short prompt along these lines (this is the actual shape
that's worked in practice):

```
You control an Android phone via: tapium '<json>'

Your job: explore this app systematically. For each screen you land on:
1. dump_ui to see what's there.
2. Tap every visible button/tab/link you haven't tried yet.
3. Note the screen name and its landmark elements in screens.md.
4. If something looks broken (error, crash, unexpected state), log it
   to bugs.md with repro steps.
5. Write a test case for anything worth covering repeatedly, appended
   to test-cases.md — never overwrite these files, only append.

Rules:
- Never tap "Pay", "Confirm", "Delete account", or any real payment/
  destructive screen — navigate up to it, note it exists, then back out.
- Prefer reset_app over manual logout to get back to a clean state.
- If a screen isn't in screens.md yet, add it before moving on.
```

The result after a session isn't just "the agent clicked around" — it's
three living documents (`screens.md`, `bugs.md`, `test-cases.md`) that
capture what the app actually does, in a form the next session (human or
agent) can build on instead of re-discovering.

**Turning a documented flow into an automated test:**

Once a flow is written down — say, in a `flows.md` with named,
step-by-step procedures — you can ask an agent to convert it directly:

> "Turn the 'Login' flow into a pytest test under `tests/login/`."

Because every Tapium action returns `"ok": true/false` and the resulting
screen state, the translation is mechanical: each documented step becomes
a `tapium.py` action call (or, if running from source, a direct Python
import — see `action_tap`, `action_dump_ui`, etc. in `tapium.py`), and
each documented outcome becomes an assertion on `"ok"` or on an element's
presence in `"screen"`. A minimal example:

```python
from tapium import connect, action_input_sequence, action_wait_for

def test_login():
    d = connect()
    result = action_input_sequence(d, {
        "steps": [
            {"field": "Email",    "text": "demo@example.com"},
            {"field": "Password", "text": "hunter2"},
            {"tap_text": "Sign in"},
        ]
    })
    assert result["ok"]

    result = action_wait_for(d, {"text": "Home", "timeout": 15})
    assert result["ok"], "Did not land on Home screen after login"
```

**Regression suites, once you have a handful of these:** group them by
name (`smoke`, `regression`, etc.) and give the agent one command to run
the whole batch and report back. What separates a *bug* from *noise* is a
judgment call worth writing down explicitly — for example: "a failed
assertion because text/behavior changed is a bug; a failure because of a
timeout or slow device is not — retry it, and only log a bug if a clean
re-run still fails." That distinction, made once in your project's
instructions, keeps an agent from either crying wolf on every flaky
network blip or silently ignoring a real regression.

**Guardrails worth writing down explicitly**, regardless of app:
- Which environments are safe to run destructive/costly actions against
  (e.g. "starting a real booking is fine on a test environment with mock
  payment providers, never on staging/prod")
- Which buttons the agent should never tap even during free exploration
  (payment confirmation, account deletion)
- What "clean state" means for your app and which action gets you there
  before each test (`reset_app` is usually the fast path — see the main
  README's action reference)

## The common thread

Both use cases follow the same shape: **Tapium supplies the see/act loop,
you (or an agent, once) supply the app-specific knowledge, written down
somewhere durable.** Neither use case needed a new Tapium action to
build — `dump_ui`, `tap`, `input_sequence`, `wait_for`, `press_key`, and
`reset_app` cover almost everything above. If you build something on top
of Tapium that doesn't fit either of these two shapes, we'd love to hear
about it — open an issue or a PR adding a section here.
