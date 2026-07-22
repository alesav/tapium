#!/usr/bin/env python3
"""
api.py — example backend API client, wired the same way as tapium.py.

This shows the intended pattern for pairing UI automation with a backend
API in agent-driven testing: use the API to set up/verify state that's
slow or flaky to reach purely through the UI (seed a test account, check
a record landed correctly, tear down test data), while tapium.py
drives the actual app.

Every request in this file is MOCKED — there is no real backend here.
Swap `_mock_request()` for real HTTP calls (e.g. via `requests`) and point
`environments.json` at your own service to adapt this to a real API.

Usage:
    python3 api.py '<json_command>'

Commands:
    get_user      {"command":"get_user","id":"user_123","env":"staging"}
                  Fetch a single user record by id.

    create_user   {"command":"create_user","email":"demo@example.com","env":"staging"}
                  Create a user and return the created record.

    list_orders   {"command":"list_orders","user_id":"user_123","env":"staging"}
                  List orders belonging to a user.

    set_mock_state {"command":"set_mock_state","id":"user_123","env":"staging",
                    "field":"verification_status","value":"blocked"}
                  Example of toggling backend-side mock state for a test
                  fixture (e.g. simulating an error condition) — the kind
                  of call a test suite uses to set up an edge case that's
                  hard to reach by driving the UI alone.

Environment config: environments.json (per-env base URL + auth token)
"""

import sys
import json
import os
import time

# ── config ────────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Falls back to the committed example config since this file ships with a
# mocked backend and no real secrets. If you point this at a real API,
# copy environments.example.json -> environments.json, fill in real
# tokens, and this will prefer that file instead (see .gitignore).
ENV_FILE = os.path.join(SCRIPT_DIR, "environments.json")
if not os.path.exists(ENV_FILE):
    ENV_FILE = os.path.join(SCRIPT_DIR, "environments.example.json")

DEFAULT_HEADERS = {
    "Accept":       "application/json",
    "Content-Type": "application/json",
}


def _load_env(env_name: str) -> dict:
    with open(ENV_FILE) as f:
        envs = json.load(f)
    if env_name not in envs:
        raise ValueError(f"Unknown env '{env_name}'. Available: {list(envs)}")
    return envs[env_name]


# ── mock backend ──────────────────────────────────────────────────────────────
# In-memory store + canned responses standing in for a real HTTP API. Replace
# `_mock_request` with real `requests`/`urllib` calls against `env["base_url"]`
# (using `env["token"]` for auth) to point this at an actual service —
# everything above and below this function is written as if it already were.
_MOCK_DB = {
    "users": {
        "user_123": {"id": "user_123", "email": "demo@example.com", "verification_status": "verified"},
    },
    "orders": {
        "user_123": [
            {"id": "order_1", "status": "completed", "amount": 19.99},
            {"id": "order_2", "status": "pending",   "amount": 4.50},
        ],
    },
}


def _mock_request(method: str, path: str, env: dict, body: dict = None) -> dict:
    """
    Stand-in for an HTTP call. Simulates basic network latency and returns
    canned/derived data from _MOCK_DB so the rest of this file can be
    written exactly as it would be against a real API.
    """
    time.sleep(0.05)  # pretend this took a network round-trip

    if method == "GET" and path.startswith("/users/"):
        user_id = path.split("/")[-1]
        user = _MOCK_DB["users"].get(user_id)
        if user is None:
            return {"status": 404, "body": {"error": f"User '{user_id}' not found"}}
        return {"status": 200, "body": user}

    if method == "POST" and path == "/users":
        new_id = f"user_{len(_MOCK_DB['users']) + 1}"
        user = {"id": new_id, "verification_status": "pending", **(body or {})}
        _MOCK_DB["users"][new_id] = user
        return {"status": 201, "body": user}

    if method == "GET" and path.startswith("/orders"):
        user_id = path.split("user_id=")[-1]
        return {"status": 200, "body": _MOCK_DB["orders"].get(user_id, [])}

    if method == "PATCH" and path.startswith("/users/"):
        user_id = path.split("/")[-1]
        user = _MOCK_DB["users"].get(user_id)
        if user is None:
            return {"status": 404, "body": {"error": f"User '{user_id}' not found"}}
        user.update(body or {})
        return {"status": 200, "body": user}

    return {"status": 404, "body": {"error": f"No mock handler for {method} {path}"}}


# ── commands ──────────────────────────────────────────────────────────────────
def cmd_get_user(params: dict) -> dict:
    user_id = params.get("id")
    env_name = params.get("env", "staging")
    if not user_id:
        return {"ok": False, "error": "get_user requires 'id'"}

    env = _load_env(env_name)
    resp = _mock_request("GET", f"/users/{user_id}", env)
    if resp["status"] != 200:
        return {"ok": False, "error": resp["body"].get("error", "request failed"), "status": resp["status"]}
    return {"ok": True, "user": resp["body"]}


def cmd_create_user(params: dict) -> dict:
    email = params.get("email")
    env_name = params.get("env", "staging")
    if not email:
        return {"ok": False, "error": "create_user requires 'email'"}

    env = _load_env(env_name)
    resp = _mock_request("POST", "/users", env, body={"email": email})
    return {"ok": resp["status"] == 201, "user": resp["body"], "status": resp["status"]}


def cmd_list_orders(params: dict) -> dict:
    user_id = params.get("user_id")
    env_name = params.get("env", "staging")
    if not user_id:
        return {"ok": False, "error": "list_orders requires 'user_id'"}

    env = _load_env(env_name)
    resp = _mock_request("GET", f"/orders?user_id={user_id}", env)
    return {"ok": True, "orders": resp["body"]}


def cmd_set_mock_state(params: dict) -> dict:
    user_id  = params.get("id")
    field    = params.get("field")
    value    = params.get("value")
    env_name = params.get("env", "staging")

    if not user_id or not field:
        return {"ok": False, "error": "set_mock_state requires 'id' and 'field'"}

    env = _load_env(env_name)
    resp = _mock_request("PATCH", f"/users/{user_id}", env, body={field: value})
    if resp["status"] != 200:
        return {"ok": False, "error": resp["body"].get("error", "request failed"), "status": resp["status"]}
    return {"ok": True, "user": resp["body"]}


COMMANDS = {
    "get_user":       cmd_get_user,
    "create_user":    cmd_create_user,
    "list_orders":    cmd_list_orders,
    "set_mock_state": cmd_set_mock_state,
}


def main() -> None:
    if len(sys.argv) < 2:
        print(json.dumps({
            "ok": False,
            "error": "No command provided. Pass a JSON string as the first argument.",
            "example": 'python3 api.py \'{"command":"get_user","id":"user_123","env":"staging"}\'',
        }))
        sys.exit(1)

    try:
        params = json.loads(sys.argv[1])
    except json.JSONDecodeError as e:
        print(json.dumps({"ok": False, "error": f"Invalid JSON: {e}"}))
        sys.exit(1)

    command = params.pop("command", None)
    if command not in COMMANDS:
        print(json.dumps({
            "ok": False,
            "error": f"Unknown command '{command}'",
            "available": list(COMMANDS.keys()),
        }))
        sys.exit(1)

    try:
        result = COMMANDS[command](params)
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}))
        sys.exit(1)

    print(json.dumps(result, indent=2))
    sys.exit(0 if result.get("ok") else 1)


if __name__ == "__main__":
    main()
