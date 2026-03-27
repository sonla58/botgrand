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
