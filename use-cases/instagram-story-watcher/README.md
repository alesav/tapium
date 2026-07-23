# Instagram Story Watcher

Scrolls a followers list and reports which accounts currently have an
active story — a **read-only monitoring script**. It does not open
stories, like anything, follow anyone, or comment. It only scrolls your
own view of a list and reads what's already visible.

## Why it stops there

The original version of this script (built while exploring what was
possible with Tapium) also opened each story and liked it, with
randomized delays to look human. That's an automated-engagement pattern
against a platform whose Terms of Use explicitly prohibit it — random
delays don't change what the action is, and it risks the account being
flagged regardless. That logic isn't included here. What's left —
detecting story presence from a list you're already scrolling — doesn't
interact with anyone else's content at all.

If you want to extend this to actually open and view stories yourself,
that's a reasonable next step (a human scrolling their own followers
list and tapping into stories is just... using the app). Just don't wire
up a loop that likes, comments, follows, or messages automatically.

## What it demonstrates

- Parsing `dump_ui`'s element list for structure that isn't in the
  `text`/`content-desc` fields Tapium surfaces directly — this needs the
  raw `resource-id` and child-node structure, so it uses
  `d.dump_hierarchy()` (the underlying `uiautomator2` device object,
  reachable via `tapium.connect()`) directly rather than only the
  `tap`/`dump_ui` actions.
- Scrolling a list and re-checking after each swipe until a match is
  found or the list is exhausted.
- Writing findings out to a durable log instead of just printing them,
  so a scheduled run leaves a record.

## Setup

```bash
pip install tapium
tapium setup
```

Log into Instagram on the connected device once, manually, before
running this — the script assumes an existing session.

## Configure

Edit the top of `watch_follower_stories.py`:

```python
TARGET_ACCOUNTS = ["some_account_you_follow"]
```

## Run

```bash
python watch_follower_stories.py
```

Output goes to stdout and appends to `story_log.csv` (created on first
run) with columns: `timestamp, target_account, username_with_story`.

## Adapting this to another app

The detection logic (`_find_all_story_avatars` in the script) is
Instagram-specific — it looks for a `FrameLayout` with resource-id
`follow_list_user_imageview` containing a second child `View` node,
which is how Instagram renders the "has an active story" ring at the
time of writing. Any app you point this at will need its own version of
that function, discovered the same way this one was: dump the UI with
and without the state you're detecting, and diff the two.
