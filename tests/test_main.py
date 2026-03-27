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
    with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "tok", "TELEGRAM_CHAT_IDS": "cid"}):
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

    with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "tok", "TELEGRAM_CHAT_IDS": "cid"}):
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

    with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "tok", "TELEGRAM_CHAT_IDS": "cid"}):
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

    with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "tok", "TELEGRAM_CHAT_IDS": "cid"}):
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

    with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "tok", "TELEGRAM_CHAT_IDS": "cid"}):
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

    with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "tok", "TELEGRAM_CHAT_IDS": "cid"}):
        run(state_path)

    with open(state_path) as f:
        state = json.load(f)
    assert state["consecutive_failures"] == 0
    assert state["failure_warning_sent"] is False
