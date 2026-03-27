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
