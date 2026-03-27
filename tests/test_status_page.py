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
