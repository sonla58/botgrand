import time
import requests


def send_message(token: str, chat_id: str, text: str) -> None:
    """Send a message via Telegram Bot API. Retries on failure with rate limit support."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}

    for attempt in range(3):
        resp = requests.post(url, data=payload, timeout=30)
        if resp.status_code == 200 and resp.json().get("ok"):
            return
        if resp.status_code == 429:
            retry_after = resp.json().get("parameters", {}).get("retry_after", 30)
            print(f"Rate limited, waiting {retry_after}s...")
            time.sleep(retry_after)
            continue
        if attempt < 2:
            print(f"Telegram send failed (status {resp.status_code}): {resp.text}, retrying in 5s...")
            time.sleep(5)

    raise RuntimeError(f"Failed to send Telegram message after 3 attempts: {resp.status_code} {resp.text}")
