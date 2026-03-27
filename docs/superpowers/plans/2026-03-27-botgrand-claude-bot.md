# Botgrand Claude Bot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Telegram notification bot that monitors Anthropic's status page and sends lifecycle alerts (new, update, resolved) to a Telegram group, deployed via GitHub Actions cron.

**Architecture:** Simple Python script per bot in a monorepo. `shared/telegram.py` handles Telegram messaging. `bots/claude_bot/main.py` fetches status page, diffs against previous state, and sends notifications. State persisted via GitHub Actions cache.

**Tech Stack:** Python 3.12, `requests`, `pytest`, GitHub Actions, Telegram Bot API

**Spec:** `docs/superpowers/specs/2026-03-27-botgrand-claude-bot-design.md`

---

## File Structure

```
botgrand/
├── bots/
│   └── claude_bot/
│       ├── __init__.py
│       ├── main.py              # Entry point — orchestrates fetch, diff, notify
│       ├── config.py            # Constants: URLs, thresholds
│       ├── status_page.py       # Fetch and parse Anthropic status page API
│       └── state.py             # Load, save, diff state; detect changes
├── shared/
│   ├── __init__.py
│   └── telegram.py              # Send messages via Telegram Bot API
├── tests/
│   ├── __init__.py
│   ├── test_telegram.py         # Tests for shared/telegram.py
│   ├── test_state.py            # Tests for bots/claude_bot/state.py
│   ├── test_status_page.py      # Tests for bots/claude_bot/status_page.py
│   └── test_main.py             # Integration test for main.py
├── .github/
│   └── workflows/
│       └── claude_bot.yml       # Cron workflow
├── requirements.txt             # requests
├── requirements-dev.txt         # pytest, responses (HTTP mocking)
└── .gitignore
```

**Design note:** `main.py` was split into `status_page.py` (fetch/parse) and `state.py` (diff/persist) to keep each file focused and testable. `main.py` orchestrates them.

**Note:** The spec lists both `incidents.json` and `summary.json` endpoints. We only use `incidents.json` because it contains all the incident data needed for diffing and notifications. `summary.json` provides component-level status but no incident details — it would only be useful if we wanted to report overall system status, which is not in scope.

---

### Task 1: Project Scaffolding

**Files:**
- Create: `.gitignore`
- Create: `requirements.txt`
- Create: `requirements-dev.txt`
- Create: `bots/__init__.py`, `bots/claude_bot/__init__.py`, `shared/__init__.py`, `tests/__init__.py`

- [ ] **Step 1: Create .gitignore**

```
__pycache__/
*.pyc
.pytest_cache/
*.egg-info/
dist/
build/
.env
venv/
state.json
```

- [ ] **Step 2: Create requirements.txt**

```
requests>=2.31,<3
```

- [ ] **Step 3: Create requirements-dev.txt**

```
-r requirements.txt
pytest>=8.0,<9
responses>=0.25,<1
```

- [ ] **Step 4: Create empty __init__.py files**

Create empty files at:
- `bots/__init__.py`
- `bots/claude_bot/__init__.py`
- `shared/__init__.py`
- `tests/__init__.py`

- [ ] **Step 5: Install dev dependencies**

Run: `pip install -r requirements-dev.txt`

- [ ] **Step 6: Verify pytest runs**

Run: `pytest --co`
Expected: "no tests ran" (collected 0 items)

- [ ] **Step 7: Commit**

```bash
git add .gitignore requirements.txt requirements-dev.txt bots/__init__.py bots/claude_bot/__init__.py shared/__init__.py tests/__init__.py
git commit -m "chore: scaffold project structure with dependencies"
```

---

### Task 2: Shared Telegram Helper

**Files:**
- Create: `shared/telegram.py`
- Create: `tests/test_telegram.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_telegram.py
import responses
import pytest
from unittest.mock import patch
from shared.telegram import send_message


FAKE_TOKEN = "123:ABC"
FAKE_CHAT_ID = "-100999"
TELEGRAM_URL = f"https://api.telegram.org/bot{FAKE_TOKEN}/sendMessage"


@responses.activate
def test_send_message_success():
    responses.add(
        responses.POST,
        TELEGRAM_URL,
        json={"ok": True, "result": {"message_id": 1}},
        status=200,
    )
    send_message(FAKE_TOKEN, FAKE_CHAT_ID, "Hello")
    assert len(responses.calls) == 1
    body = responses.calls[0].request.body
    assert "Hello" in body


@responses.activate
@patch("shared.telegram.time.sleep")
def test_send_message_retry_on_failure_then_success(mock_sleep):
    responses.add(responses.POST, TELEGRAM_URL, json={"ok": False}, status=500)
    responses.add(
        responses.POST,
        TELEGRAM_URL,
        json={"ok": True, "result": {"message_id": 2}},
        status=200,
    )
    send_message(FAKE_TOKEN, FAKE_CHAT_ID, "Retry test")
    assert len(responses.calls) == 2
    mock_sleep.assert_called_once_with(5)


@responses.activate
@patch("shared.telegram.time.sleep")
def test_send_message_raises_after_retry_exhausted(mock_sleep):
    responses.add(responses.POST, TELEGRAM_URL, json={"ok": False}, status=500)
    responses.add(responses.POST, TELEGRAM_URL, json={"ok": False}, status=500)
    with pytest.raises(RuntimeError, match="Failed to send Telegram message"):
        send_message(FAKE_TOKEN, FAKE_CHAT_ID, "Fail test")
    assert len(responses.calls) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_telegram.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement shared/telegram.py**

```python
# shared/telegram.py
import time
import requests


def send_message(token: str, chat_id: str, text: str) -> None:
    """Send a message via Telegram Bot API. Retries once on failure."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}

    for attempt in range(2):
        resp = requests.post(url, data=payload, timeout=30)
        if resp.status_code == 200 and resp.json().get("ok"):
            return
        if attempt == 0:
            print(f"Telegram send failed (status {resp.status_code}), retrying in 5s...")
            time.sleep(5)

    raise RuntimeError(f"Failed to send Telegram message after 2 attempts: {resp.status_code}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_telegram.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add shared/telegram.py tests/test_telegram.py
git commit -m "feat: add shared Telegram helper with retry logic"
```

---

### Task 3: Bot Config

**Files:**
- Create: `bots/claude_bot/config.py`

- [ ] **Step 1: Create config.py**

```python
# bots/claude_bot/config.py

STATUS_PAGE_URL = "https://status.anthropic.com/api/v2/incidents.json"
CONSECUTIVE_FAILURE_THRESHOLD = 3
RESOLVED_RETENTION_HOURS = 24
```

- [ ] **Step 2: Commit**

```bash
git add bots/claude_bot/config.py
git commit -m "feat: add claude_bot config constants"
```

---

### Task 4: State Management

**Files:**
- Create: `bots/claude_bot/state.py`
- Create: `tests/test_state.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_state.py
import json
import os
import pytest
from datetime import datetime, timezone, timedelta
from bots.claude_bot.state import load_state, save_state, diff_state, empty_state, cleanup_resolved


def test_empty_state():
    state = empty_state()
    assert state["incidents"] == {}
    assert state["consecutive_failures"] == 0
    assert state["failure_warning_sent"] is False
    assert state["initialized"] is False


def test_save_and_load_state(tmp_path):
    path = tmp_path / "state.json"
    state = empty_state()
    state["incidents"]["abc"] = {
        "name": "Test",
        "status": "investigating",
        "last_update_id": "u1",
        "last_update_at": "2026-03-27T10:00:00Z",
        "resolved_at": None,
        "shortlink": "https://status.anthropic.com/incidents/abc",
        "affected_components": ["Claude API"],
    }
    save_state(state, str(path))
    loaded = load_state(str(path))
    assert loaded == state


def test_load_state_missing_file(tmp_path):
    path = tmp_path / "nonexistent.json"
    state = load_state(str(path))
    assert state == empty_state()


def test_diff_new_incident():
    old = empty_state()
    new = empty_state()
    new["incidents"]["abc"] = {
        "name": "Outage",
        "status": "investigating",
        "last_update_id": "u1",
        "last_update_at": "2026-03-27T10:00:00Z",
        "resolved_at": None,
        "shortlink": "https://example.com/incidents/abc",
        "affected_components": ["API"],
        "latest_update_body": "We are investigating.",
    }
    changes = diff_state(old, new)
    assert len(changes) == 1
    assert changes[0]["type"] == "new"
    assert changes[0]["incident"]["name"] == "Outage"


def test_diff_updated_incident():
    old = empty_state()
    old["incidents"]["abc"] = {
        "name": "Outage",
        "status": "investigating",
        "last_update_id": "u1",
        "last_update_at": "2026-03-27T10:00:00Z",
        "resolved_at": None,
        "shortlink": "https://example.com/incidents/abc",
        "affected_components": ["API"],
        "latest_update_body": "Investigating.",
    }
    new = empty_state()
    new["incidents"]["abc"] = {
        "name": "Outage",
        "status": "identified",
        "last_update_id": "u2",
        "last_update_at": "2026-03-27T10:30:00Z",
        "resolved_at": None,
        "shortlink": "https://example.com/incidents/abc",
        "affected_components": ["API"],
        "latest_update_body": "Fix identified.",
    }
    changes = diff_state(old, new)
    assert len(changes) == 1
    assert changes[0]["type"] == "updated"


def test_diff_resolved_incident():
    old = empty_state()
    old["incidents"]["abc"] = {
        "name": "Outage",
        "status": "investigating",
        "last_update_id": "u1",
        "last_update_at": "2026-03-27T10:00:00Z",
        "resolved_at": None,
        "shortlink": "https://example.com/incidents/abc",
        "affected_components": ["API"],
        "latest_update_body": "Investigating.",
    }
    new = empty_state()
    new["incidents"]["abc"] = {
        "name": "Outage",
        "status": "resolved",
        "last_update_id": "u3",
        "last_update_at": "2026-03-27T11:00:00Z",
        "resolved_at": "2026-03-27T11:00:00Z",
        "shortlink": "https://example.com/incidents/abc",
        "affected_components": ["API"],
        "latest_update_body": "Resolved.",
    }
    changes = diff_state(old, new)
    assert len(changes) == 1
    assert changes[0]["type"] == "resolved"


def test_diff_postmortem_treated_as_update():
    old = empty_state()
    old["incidents"]["abc"] = {
        "name": "Outage",
        "status": "resolved",
        "last_update_id": "u2",
        "last_update_at": "2026-03-27T11:00:00Z",
        "resolved_at": "2026-03-27T11:00:00Z",
        "shortlink": "https://example.com/incidents/abc",
        "affected_components": ["API"],
        "latest_update_body": "Resolved.",
    }
    new = empty_state()
    new["incidents"]["abc"] = {
        "name": "Outage",
        "status": "postmortem",
        "last_update_id": "u3",
        "last_update_at": "2026-03-27T12:00:00Z",
        "resolved_at": "2026-03-27T11:00:00Z",
        "shortlink": "https://example.com/incidents/abc",
        "affected_components": ["API"],
        "latest_update_body": "Postmortem published.",
    }
    changes = diff_state(old, new)
    assert len(changes) == 1
    assert changes[0]["type"] == "updated"


def test_diff_no_changes():
    old = empty_state()
    old["incidents"]["abc"] = {
        "name": "Outage",
        "status": "investigating",
        "last_update_id": "u1",
        "last_update_at": "2026-03-27T10:00:00Z",
        "resolved_at": None,
        "shortlink": "https://example.com/incidents/abc",
        "affected_components": ["API"],
        "latest_update_body": "Investigating.",
    }
    changes = diff_state(old, old)
    assert len(changes) == 0


def test_cleanup_resolved_removes_old():
    state = empty_state()
    old_time = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
    state["incidents"]["abc"] = {
        "name": "Old",
        "status": "resolved",
        "last_update_id": "u1",
        "last_update_at": old_time,
        "resolved_at": old_time,
        "shortlink": "https://example.com/incidents/abc",
        "affected_components": ["API"],
    }
    cleanup_resolved(state)
    assert "abc" not in state["incidents"]


def test_cleanup_resolved_keeps_recent():
    state = empty_state()
    recent_time = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    state["incidents"]["abc"] = {
        "name": "Recent",
        "status": "resolved",
        "last_update_id": "u1",
        "last_update_at": recent_time,
        "resolved_at": recent_time,
        "shortlink": "https://example.com/incidents/abc",
        "affected_components": ["API"],
    }
    cleanup_resolved(state)
    assert "abc" in state["incidents"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_state.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement state.py**

```python
# bots/claude_bot/state.py
import json
import os
from datetime import datetime, timezone, timedelta
from bots.claude_bot.config import RESOLVED_RETENTION_HOURS


def empty_state() -> dict:
    return {
        "incidents": {},
        "consecutive_failures": 0,
        "failure_warning_sent": False,
        "initialized": False,
    }


def load_state(path: str) -> dict:
    if not os.path.exists(path):
        return empty_state()
    with open(path) as f:
        return json.load(f)


def save_state(state: dict, path: str) -> None:
    with open(path, "w") as f:
        json.dump(state, f, indent=2)


def diff_state(old: dict, new: dict) -> list[dict]:
    changes = []
    old_incidents = old.get("incidents", {})
    new_incidents = new.get("incidents", {})

    for inc_id, inc in new_incidents.items():
        if inc_id not in old_incidents:
            changes.append({"type": "new", "incident": inc})
        elif inc["last_update_id"] != old_incidents[inc_id]["last_update_id"]:
            if inc["status"] == "resolved":
                changes.append({"type": "resolved", "incident": inc})
            else:
                # postmortem and all other status changes are updates
                changes.append({"type": "updated", "incident": inc})

    return changes


def cleanup_resolved(state: dict) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=RESOLVED_RETENTION_HOURS)
    to_remove = []
    for inc_id, inc in state["incidents"].items():
        if inc.get("resolved_at"):
            resolved_at = datetime.fromisoformat(inc["resolved_at"])
            if resolved_at < cutoff:
                to_remove.append(inc_id)
    for inc_id in to_remove:
        del state["incidents"][inc_id]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_state.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add bots/claude_bot/state.py tests/test_state.py
git commit -m "feat: add state management with diffing and cleanup"
```

---

### Task 5: Status Page Fetcher

**Files:**
- Create: `bots/claude_bot/status_page.py`
- Create: `tests/test_status_page.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_status_page.py
import responses
import pytest
from bots.claude_bot.status_page import fetch_incidents
from bots.claude_bot.config import STATUS_PAGE_URL


SAMPLE_RESPONSE = {
    "incidents": [
        {
            "id": "abc123",
            "name": "Degraded API Performance",
            "status": "investigating",
            "shortlink": "https://stspg.io/abc123",
            "incident_updates": [
                {
                    "id": "upd_2",
                    "status": "investigating",
                    "body": "We are continuing to investigate.",
                    "updated_at": "2026-03-27T10:30:00.000Z",
                },
                {
                    "id": "upd_1",
                    "status": "investigating",
                    "body": "We are investigating reports.",
                    "updated_at": "2026-03-27T10:00:00.000Z",
                },
            ],
            "components": [
                {"name": "Claude API"},
                {"name": "claude.ai"},
            ],
        }
    ]
}


@responses.activate
def test_fetch_incidents_success():
    responses.add(responses.GET, STATUS_PAGE_URL, json=SAMPLE_RESPONSE, status=200)
    incidents = fetch_incidents()
    assert "abc123" in incidents
    inc = incidents["abc123"]
    assert inc["name"] == "Degraded API Performance"
    assert inc["status"] == "investigating"
    assert inc["last_update_id"] == "upd_2"
    assert inc["shortlink"] == "https://stspg.io/abc123"
    assert inc["affected_components"] == ["Claude API", "claude.ai"]
    assert inc["latest_update_body"] == "We are continuing to investigate."


@responses.activate
def test_fetch_incidents_empty():
    responses.add(responses.GET, STATUS_PAGE_URL, json={"incidents": []}, status=200)
    incidents = fetch_incidents()
    assert incidents == {}


@responses.activate
def test_fetch_incidents_http_error():
    responses.add(responses.GET, STATUS_PAGE_URL, status=500)
    with pytest.raises(Exception):
        fetch_incidents()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_status_page.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement status_page.py**

```python
# bots/claude_bot/status_page.py
import requests
from bots.claude_bot.config import STATUS_PAGE_URL


def fetch_incidents() -> dict:
    """Fetch unresolved incidents from Anthropic status page.

    Returns a dict keyed by incident ID, matching the state format.
    """
    resp = requests.get(STATUS_PAGE_URL, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    incidents = {}
    for inc in data.get("incidents", []):
        updates = inc.get("incident_updates", [])
        latest = updates[0] if updates else {}
        resolved_statuses = ("resolved", "postmortem")

        incidents[inc["id"]] = {
            "name": inc["name"],
            "status": inc["status"],
            "last_update_id": latest.get("id", ""),
            "last_update_at": latest.get("updated_at", ""),
            "resolved_at": latest.get("updated_at") if inc["status"] in resolved_statuses else None,
            "shortlink": inc.get("shortlink", ""),
            "affected_components": [c["name"] for c in inc.get("components", [])],
            "latest_update_body": latest.get("body", ""),
        }

    return incidents
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_status_page.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add bots/claude_bot/status_page.py tests/test_status_page.py
git commit -m "feat: add status page fetcher with incident parsing"
```

---

### Task 6: Main Orchestrator

**Files:**
- Create: `bots/claude_bot/main.py`
- Create: `tests/test_main.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_main.py
import json
import os
import responses
import pytest
from unittest.mock import patch
from bots.claude_bot.main import run, format_message
from bots.claude_bot.config import STATUS_PAGE_URL


TELEGRAM_URL = "https://api.telegram.org/bot{token}/sendMessage"


def test_format_message_new():
    inc = {
        "name": "API Outage",
        "status": "investigating",
        "affected_components": ["Claude API"],
        "latest_update_body": "We are investigating.",
        "shortlink": "https://stspg.io/abc",
    }
    msg = format_message("new", inc)
    assert "🔴" in msg
    assert "API Outage" in msg
    assert "Investigating" in msg
    assert "https://stspg.io/abc" in msg


def test_format_message_updated():
    inc = {
        "name": "API Outage",
        "status": "identified",
        "affected_components": ["Claude API"],
        "latest_update_body": "Fix identified.",
        "shortlink": "https://stspg.io/abc",
    }
    msg = format_message("updated", inc)
    assert "🟡" in msg
    assert "Update" in msg


def test_format_message_resolved():
    inc = {
        "name": "API Outage",
        "status": "resolved",
        "affected_components": ["Claude API"],
        "latest_update_body": "Resolved.",
        "shortlink": "https://stspg.io/abc",
    }
    msg = format_message("resolved", inc)
    assert "🟢" in msg
    assert "Resolved" in msg


@responses.activate
def test_run_first_run_no_notifications(tmp_path):
    """First run should save state but NOT send any Telegram messages."""
    state_path = str(tmp_path / "state.json")
    responses.add(
        responses.GET,
        STATUS_PAGE_URL,
        json={
            "incidents": [
                {
                    "id": "abc",
                    "name": "Outage",
                    "status": "investigating",
                    "shortlink": "https://stspg.io/abc",
                    "incident_updates": [
                        {"id": "u1", "status": "investigating", "body": "Looking.", "updated_at": "2026-03-27T10:00:00Z"}
                    ],
                    "components": [{"name": "API"}],
                }
            ]
        },
        status=200,
    )
    with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "tok", "TELEGRAM_CHAT_ID": "cid"}):
        run(state_path)
    # No Telegram calls should have been made
    assert len([c for c in responses.calls if "telegram" in c.request.url]) == 0
    # State should be saved
    assert os.path.exists(state_path)


@responses.activate
def test_run_new_incident_sends_notification(tmp_path):
    """When a new incident appears, send a Telegram notification."""
    state_path = str(tmp_path / "state.json")
    # Write empty previous state (initialized=True so it's not treated as first run)
    with open(state_path, "w") as f:
        json.dump({"incidents": {}, "consecutive_failures": 0, "failure_warning_sent": False, "initialized": True}, f)

    responses.add(
        responses.GET,
        STATUS_PAGE_URL,
        json={
            "incidents": [
                {
                    "id": "abc",
                    "name": "Outage",
                    "status": "investigating",
                    "shortlink": "https://stspg.io/abc",
                    "incident_updates": [
                        {"id": "u1", "status": "investigating", "body": "Looking.", "updated_at": "2026-03-27T10:00:00Z"}
                    ],
                    "components": [{"name": "API"}],
                }
            ]
        },
        status=200,
    )
    responses.add(
        responses.POST,
        "https://api.telegram.org/bottok/sendMessage",
        json={"ok": True, "result": {"message_id": 1}},
        status=200,
    )

    with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "tok", "TELEGRAM_CHAT_ID": "cid"}):
        run(state_path)
    telegram_calls = [c for c in responses.calls if "telegram" in c.request.url]
    assert len(telegram_calls) == 1


@responses.activate
def test_run_fetch_failure_increments_counter(tmp_path):
    """When status page is unreachable, increment failure counter."""
    state_path = str(tmp_path / "state.json")
    with open(state_path, "w") as f:
        json.dump({"incidents": {}, "consecutive_failures": 0, "failure_warning_sent": False, "initialized": True}, f)

    responses.add(responses.GET, STATUS_PAGE_URL, status=500)

    with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "tok", "TELEGRAM_CHAT_ID": "cid"}):
        run(state_path)

    with open(state_path) as f:
        state = json.load(f)
    assert state["consecutive_failures"] == 1


@responses.activate
def test_run_sends_warning_at_failure_threshold(tmp_path):
    """After 3 consecutive failures, send a Telegram warning."""
    state_path = str(tmp_path / "state.json")
    with open(state_path, "w") as f:
        json.dump({"incidents": {}, "consecutive_failures": 2, "failure_warning_sent": False, "initialized": True}, f)

    responses.add(responses.GET, STATUS_PAGE_URL, status=500)
    responses.add(
        responses.POST,
        "https://api.telegram.org/bottok/sendMessage",
        json={"ok": True, "result": {"message_id": 1}},
        status=200,
    )

    with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "tok", "TELEGRAM_CHAT_ID": "cid"}):
        run(state_path)

    telegram_calls = [c for c in responses.calls if "telegram" in c.request.url]
    assert len(telegram_calls) == 1

    with open(state_path) as f:
        state = json.load(f)
    assert state["consecutive_failures"] == 3
    assert state["failure_warning_sent"] is True


@responses.activate
def test_run_no_duplicate_failure_warning(tmp_path):
    """Once warning is sent, don't send again on subsequent failures."""
    state_path = str(tmp_path / "state.json")
    with open(state_path, "w") as f:
        json.dump({"incidents": {}, "consecutive_failures": 3, "failure_warning_sent": True, "initialized": True}, f)

    responses.add(responses.GET, STATUS_PAGE_URL, status=500)

    with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "tok", "TELEGRAM_CHAT_ID": "cid"}):
        run(state_path)

    telegram_calls = [c for c in responses.calls if "telegram" in c.request.url]
    assert len(telegram_calls) == 0

    with open(state_path) as f:
        state = json.load(f)
    assert state["consecutive_failures"] == 4


@responses.activate
def test_run_resets_failure_counters_on_success(tmp_path):
    """Successful fetch resets failure tracking."""
    state_path = str(tmp_path / "state.json")
    with open(state_path, "w") as f:
        json.dump({"incidents": {}, "consecutive_failures": 5, "failure_warning_sent": True, "initialized": True}, f)

    responses.add(responses.GET, STATUS_PAGE_URL, json={"incidents": []}, status=200)

    with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "tok", "TELEGRAM_CHAT_ID": "cid"}):
        run(state_path)

    with open(state_path) as f:
        state = json.load(f)
    assert state["consecutive_failures"] == 0
    assert state["failure_warning_sent"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_main.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement main.py**

```python
# bots/claude_bot/main.py
import os
import sys
from bots.claude_bot.config import CONSECUTIVE_FAILURE_THRESHOLD
from bots.claude_bot.state import load_state, save_state, diff_state, empty_state, cleanup_resolved
from bots.claude_bot.status_page import fetch_incidents
from shared.telegram import send_message


def format_message(change_type: str, incident: dict) -> str:
    name = incident["name"]
    status = incident.get("status", "unknown").replace("_", " ").title()
    components = ", ".join(incident.get("affected_components", []))
    body = incident.get("latest_update_body", "")
    link = incident.get("shortlink", "https://status.anthropic.com")

    if change_type == "new":
        lines = [
            f"🔴 <b>New Incident: {name}</b>",
            f"Status: {status}",
        ]
        if components:
            lines.append(f"Affected: {components}")
        if body:
            lines.append(f"Details: {body}")
        lines.append(f"🔗 {link}")
        return "\n".join(lines)

    if change_type == "resolved":
        lines = [
            f"🟢 <b>Resolved: {name}</b>",
        ]
        if body:
            lines.append(body)
        lines.append(f"🔗 {link}")
        return "\n".join(lines)

    # updated (including postmortem)
    lines = [
        f"🟡 <b>Update: {name}</b>",
        f"Status: {status}",
    ]
    if body:
        lines.append(body)
    lines.append(f"🔗 {link}")
    return "\n".join(lines)


def run(state_path: str = "state.json") -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]

    state = load_state(state_path)
    is_first_run = not state.get("initialized", False)

    try:
        current_incidents = fetch_incidents()
    except Exception as e:
        print(f"Failed to fetch status page: {e}")
        state["consecutive_failures"] += 1

        if (
            state["consecutive_failures"] >= CONSECUTIVE_FAILURE_THRESHOLD
            and not state["failure_warning_sent"]
        ):
            send_message(
                token,
                chat_id,
                f"⚠️ <b>Warning:</b> Anthropic status page unreachable for {state['consecutive_failures']} consecutive checks.",
            )
            state["failure_warning_sent"] = True

        save_state(state, state_path)
        return

    # Reset failure tracking on success
    state["consecutive_failures"] = 0
    state["failure_warning_sent"] = False

    # Build new state from current incidents
    new_state = empty_state()
    new_state["incidents"] = current_incidents

    if is_first_run:
        print("First run — loading current state without notifications.")
    else:
        changes = diff_state(state, new_state)
        for change in changes:
            msg = format_message(change["type"], change["incident"])
            print(f"Sending notification: {change['type']} — {change['incident']['name']}")
            send_message(token, chat_id, msg)

    # Mark as initialized and clean up old resolved incidents
    new_state["initialized"] = True
    cleanup_resolved(new_state)
    save_state(new_state, state_path)


if __name__ == "__main__":
    state_path = os.environ.get("STATE_PATH", "state.json")
    run(state_path)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_main.py -v`
Expected: 9 passed

- [ ] **Step 5: Run all tests**

Run: `pytest -v`
Expected: All tests pass (24 total)

- [ ] **Step 6: Commit**

```bash
git add bots/claude_bot/main.py tests/test_main.py
git commit -m "feat: add main orchestrator with message formatting"
```

---

### Task 7: GitHub Actions Workflow

**Files:**
- Create: `.github/workflows/claude_bot.yml`

- [ ] **Step 1: Create the workflow file**

```yaml
# .github/workflows/claude_bot.yml
name: Claude Bot - Status Monitor

on:
  schedule:
    - cron: '*/15 * * * *'
  workflow_dispatch:

jobs:
  check-status:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Restore state
        uses: actions/cache/restore@v4
        with:
          path: state.json
          key: claude-bot-state-v1-${{ github.run_id }}
          restore-keys: |
            claude-bot-state-v1-

      - name: Run claude_bot
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
          STATE_PATH: state.json
        run: python -m bots.claude_bot.main

      - name: Save state
        uses: actions/cache/save@v4
        if: always()
        with:
          path: state.json
          key: claude-bot-state-v1-${{ github.run_id }}
```

- [ ] **Step 2: Validate YAML syntax**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/claude_bot.yml'))" 2>&1 || echo "Install pyyaml: pip install pyyaml && retry"`

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/claude_bot.yml
git commit -m "feat: add GitHub Actions workflow for claude_bot (15-min cron)"
```

---

### Task 8: Final Verification

- [ ] **Step 1: Run full test suite**

Run: `pytest -v --tb=short`
Expected: All 24 tests pass

- [ ] **Step 2: Verify project structure**

Run: `find . -type f -not -path './.git/*' | sort`
Expected: All planned files present

- [ ] **Step 3: Commit any remaining changes**

If any files were missed, stage and commit them.
