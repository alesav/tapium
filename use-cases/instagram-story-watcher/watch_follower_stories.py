"""
watch_follower_stories.py — read-only story detection.

Scrolls a target account's followers list and reports which followers
currently have an active story. Does not open stories, like, comment,
follow, or message — see README.md for why.

Run:
    python watch_follower_stories.py
"""

import csv
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import tapium as agent

# --- Config ---------------------------------------------------------
TARGET_ACCOUNTS = [
    "some_account_you_follow",
]
MAX_SCROLLS = 20
LOG_PATH = Path(__file__).parent / "story_log.csv"
# ---------------------------------------------------------------------

AVATAR_ROW_ID = "com.instagram.android:id/follow_list_user_imageview"
USERNAME_ID = "com.instagram.android:id/follow_list_username"
SEARCH_EDIT_ID = "com.instagram.android:id/action_bar_search_edit_text"


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def _open_followers_list(d, target_account: str) -> None:
    log(f"Navigating to followers list of @{target_account}")
    d.app_start("com.instagram.android")
    agent.wait_idle(d, timeout=3)

    nav_tab = d(description="Search and explore")
    for _ in range(6):
        if nav_tab.exists:
            break
        d.press("back")
        agent.wait_idle(d, timeout=2)
    assert nav_tab.exists, "Could not reach Search and explore tab"
    nav_tab.click()
    agent.wait_idle(d)

    search_box = d(resourceId=SEARCH_EDIT_ID)
    assert search_box.wait(timeout=8), "Instagram search bar not found"
    search_box.click()
    search_box.set_text(target_account)
    agent.wait_idle(d, timeout=3)

    row = d(resourceId="com.instagram.android:id/row_search_user_container", instance=0)
    assert row.wait(timeout=8), f"Search result for '{target_account}' not found"
    row.click()
    agent.wait_idle(d)

    followers_btn = d(textContains="followers")
    assert followers_btn.wait(timeout=10), "Followers button not found"
    followers_btn.click()
    agent.wait_idle(d)

    assert d(resourceId="android:id/list").exists(timeout=8), "Followers list did not load"
    log("Followers list loaded")


def _find_all_story_avatars(xml_str: str) -> list[tuple]:
    """
    Return [(username, bounds), ...] for every follower row currently
    on screen that has an active story ring.

    Detection: a follower row's avatar container is a FrameLayout with
    resource-id `follow_list_user_imageview`. With an active story it
    has TWO children (a story-ring View + the ImageView); without one,
    just the ImageView.
    """
    root = ET.fromstring(xml_str)
    username_nodes = [n for n in root.iter() if n.attrib.get("resource-id") == USERNAME_ID]

    found = []
    for node in root.iter():
        if node.attrib.get("resource-id") != AVATAR_ROW_ID:
            continue
        if node.attrib.get("class") != "android.widget.FrameLayout":
            continue
        children = list(node)
        has_ring = any(c.attrib.get("class") == "android.view.View" for c in children)
        if not has_ring:
            continue

        bounds = node.attrib.get("bounds", "")
        center = agent._bounds_center(bounds)
        username = None
        if center:
            _, avatar_cy = center
            for uname_node in username_nodes:
                ub = agent._bounds_center(uname_node.attrib.get("bounds", ""))
                if ub and abs(ub[1] - avatar_cy) < 60:
                    username = uname_node.attrib.get("text", "").strip()
                    break
        found.append((username or "<unknown>", bounds))
    return found


def _scroll_followers_list(d) -> None:
    lv = d(resourceId="android:id/list")
    if not lv.exists(timeout=1):
        return
    b = lv.info["bounds"]
    mid_x = (b["left"] + b["right"]) // 2
    from_y = int(b["bottom"] * 0.75 + b["top"] * 0.25)
    to_y = int(b["bottom"] * 0.25 + b["top"] * 0.75)
    d.swipe(mid_x, from_y, mid_x, to_y, duration=0.3)
    agent.wait_idle(d)


def _log_result(target_account: str, usernames: set[str]) -> None:
    is_new = not LOG_PATH.exists()
    with open(LOG_PATH, "a", newline="") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(["timestamp", "target_account", "username_with_story"])
        ts = datetime.now(timezone.utc).isoformat()
        for username in sorted(usernames):
            writer.writerow([ts, target_account, username])


def watch_account(d, target_account: str) -> set[str]:
    _open_followers_list(d, target_account)

    seen: set[str] = set()
    seen_bounds: set[str] = set()

    for scroll_n in range(MAX_SCROLLS):
        xml = d.dump_hierarchy()
        avatars = _find_all_story_avatars(xml)

        new_this_scroll = 0
        for username, bounds in avatars:
            if bounds in seen_bounds:
                continue
            seen_bounds.add(bounds)
            seen.add(username)
            new_this_scroll += 1

        if new_this_scroll:
            log(f"  scroll {scroll_n}: +{new_this_scroll} new (total {len(seen)})")

        _scroll_followers_list(d)
        time.sleep(0.4)

    log(f"@{target_account}: {len(seen)} follower(s) with an active story: {sorted(seen)}")
    return seen


def main():
    d = agent.connect()
    agent.ensure_screen_on(d)

    for target_account in TARGET_ACCOUNTS:
        usernames = watch_account(d, target_account)
        _log_result(target_account, usernames)

    log(f"Done. Results appended to {LOG_PATH}")


if __name__ == "__main__":
    main()
