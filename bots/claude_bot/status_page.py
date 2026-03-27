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
