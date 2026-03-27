"""Get chat IDs from recent messages received by your bot.

Usage: python scripts/get_chat_id.py --token YOUR_BOT_TOKEN

Before running: send a message in the group where the bot is a member.
"""
import argparse
import requests


def main():
    parser = argparse.ArgumentParser(description="Get Telegram chat IDs for your bot")
    parser.add_argument("--token", required=True, help="Telegram bot token")
    args = parser.parse_args()

    resp = requests.get(f"https://api.telegram.org/bot{args.token}/getUpdates", timeout=30)
    data = resp.json()

    if not data.get("ok"):
        print(f"Error: {data}")
        return

    results = data.get("result", [])
    if not results:
        print("No updates found. Send a message in the group first, then re-run.")
        return

    seen = set()
    for update in results:
        msg = update.get("message") or update.get("my_chat_member", {}).get("chat")
        if not msg:
            continue
        chat = msg.get("chat") or msg
        chat_id = chat.get("id")
        title = chat.get("title", chat.get("first_name", "Unknown"))
        chat_type = chat.get("type", "unknown")
        if chat_id and chat_id not in seen:
            seen.add(chat_id)
            print(f"  Chat ID: {chat_id}  |  Type: {chat_type}  |  Name: {title}")

    if not seen:
        print("No chats found in updates. Make sure the bot is in the group and someone sent a message.")


if __name__ == "__main__":
    main()
