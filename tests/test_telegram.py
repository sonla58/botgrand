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
