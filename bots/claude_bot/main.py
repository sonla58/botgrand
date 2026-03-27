# bots/claude_bot/main.py
import os
import sys
from html import escape
from bots.claude_bot.config import CONSECUTIVE_FAILURE_THRESHOLD
from bots.claude_bot.state import load_state, save_state, diff_state, empty_state, cleanup_resolved
from bots.claude_bot.status_page import fetch_incidents
from shared.telegram import send_message


def format_message(change_type: str, incident: dict) -> str:
    name = escape(incident["name"])
    status = escape(incident.get("status", "unknown").replace("_", " ").title())
    components = escape(", ".join(incident.get("affected_components", [])))
    body = escape(incident.get("latest_update_body", ""))
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
    chat_ids = [cid.strip() for cid in os.environ["TELEGRAM_CHAT_IDS"].split(",") if cid.strip()]

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
            for cid in chat_ids:
                send_message(
                    token,
                    cid,
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
            for cid in chat_ids:
                send_message(token, cid, msg)

    # Mark as initialized and clean up old resolved incidents
    new_state["initialized"] = True
    cleanup_resolved(new_state)
    save_state(new_state, state_path)


if __name__ == "__main__":
    state_path = os.environ.get("STATE_PATH", "state.json")
    run(state_path)
