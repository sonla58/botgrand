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
