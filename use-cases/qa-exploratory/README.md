# QA Exploratory Testing

An agent prompt plus a small file layout for exploratory testing: point
an agent at an app it hasn't seen, have it explore systematically, and
have it keep three living documents up to date as it goes. Then use the
same layout to turn a documented flow into a real automated test.

## Files here

| File | Purpose |
|---|---|
| `exploratory_prompt.md` | The prompt to give an agent for a session |
| `screens.md` | Template — registry of discovered screens (agent appends) |
| `bugs.md` | Template — bug log (agent appends) |
| `test-cases.md` | Template — test cases found during exploration (agent appends) |
| `test_login_example.py` | A worked example: a documented "Login" flow turned into a pytest test |

## Running an exploratory session

1. Connect a device, run `tapium setup` once (see the main README).
2. Copy `screens.md`, `bugs.md`, and `test-cases.md` into your own
   project — these are meant to accumulate over many sessions, so they
   shouldn't live inside this examples folder long-term.
3. Give an agent the contents of `exploratory_prompt.md` as its system
   prompt (fill in the placeholders), plus tool access to run
   `tapium '<json>'` as a shell command.
4. Let it explore. Review `bugs.md` and `test-cases.md` afterward —
   these are notes to review, not authoritative until you've checked
   them.

## Turning a documented flow into a test

Once `test-cases.md` (or a `flows.md` you maintain alongside it) has a
flow written out step by step, ask an agent (or write it yourself) to
translate it into a `pytest` test the same shape as
`test_login_example.py`: each documented step becomes one Tapium action
call, each documented expected outcome becomes an assertion on `"ok"` or
on the returned `"screen"` contents.

## A note on regression suites

Once you have several of these tests, group them (`smoke`, `regression`,
...) and give an agent one command to run a batch and report back. Worth
deciding — and writing down, the same way this folder's files are
written down — what counts as a real bug versus noise: a failed
assertion because text or behavior changed is a bug; a failure from a
timeout, network blip, or slow device is not — retry once, and only log
it if a clean re-run still fails.

Also worth deciding up front and writing somewhere an agent will read
it: which environments are safe for destructive or costly actions (real
payments, real bookings, real account deletion), and which buttons the
agent should never tap even during free exploration.
