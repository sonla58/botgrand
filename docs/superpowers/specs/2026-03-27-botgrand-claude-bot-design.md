# Botgrand: Multi-Bot Platform & Claude Bot Design

**Date:** 2026-03-27
**Status:** Approved

## Overview

Botgrand is a monorepo hosting multiple bots deployed on GitHub Actions infrastructure. Each bot lives in its own directory under `bots/`, sharing common utilities from `shared/`. The first bot, `claude_bot`, monitors Anthropic's status page and sends lifecycle notifications to a Telegram group when Claude services experience incidents.

## Repository Structure

```
botgrand/
├── bots/
│   └── claude_bot/
│       ├── main.py              # Entry point — fetch, diff, notify
│       └── config.py            # Bot-specific config (poll URL, component filters)
├── shared/
│   └── telegram.py              # Send messages to Telegram via Bot API
├── .github/
│   └── workflows/
│       └── claude_bot.yml       # Cron workflow, runs every 15 min
├── requirements.txt             # Shared + bot dependencies
└── README.md
```

Future bots follow the same pattern: add a directory under `bots/` and a corresponding workflow under `.github/workflows/`.

## Status Page Polling & State Diffing

### Data Source

Fetch from the Anthropic status page JSON API:
- `https://status.anthropic.com/api/v2/incidents.json` — unresolved incidents
- `https://status.anthropic.com/api/v2/summary.json` — overall summary

These are standard Atlassian Statuspage endpoints.

### State Tracking

After each run, the current incident state is saved and persisted via GitHub Actions cache (keyed by bot name). On the next run, the previous state is loaded and compared.

Three types of changes are detected:
- **New incident** — incident ID not present in previous state
- **Updated incident** — same ID but a new status update entry (e.g., investigating → identified → monitoring)
- **Resolved incident** — incident status moved to "resolved" or "postmortem"

### State Format (`state.json`)

```json
{
  "incidents": {
    "abc123": {
      "name": "Degraded API Performance",
      "status": "investigating",
      "last_update_id": "upd_456",
      "last_update_at": "2026-03-27T10:00:00Z"
    }
  },
  "consecutive_failures": 0
}
```

The diff logic compares incident IDs and `last_update_id` to detect changes.

## Telegram Notifications

### Shared Helper (`shared/telegram.py`)

- Accepts bot token and chat ID from environment variables
- Sends formatted messages via Telegram Bot API `sendMessage` endpoint with HTML parse mode

### Message Formats

**New incident:**
```
🔴 New Incident: Degraded API Performance
Status: Investigating
Affected: Claude API, claude.ai
Details: We are investigating reports of increased latency...
🔗 https://status.anthropic.com
```

**Update:**
```
🟡 Update: Degraded API Performance
Status: Identified
The issue has been identified and a fix is being deployed...
🔗 https://status.anthropic.com
```

**Resolved:**
```
🟢 Resolved: Degraded API Performance
This incident has been resolved.
🔗 https://status.anthropic.com
```

### Secrets Required (GitHub Repo Secrets)

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

## GitHub Actions Workflow

### `.github/workflows/claude_bot.yml`

- **Trigger:** `schedule: cron: '*/15 * * * *'` + `workflow_dispatch` for manual runs
- **Runner:** `ubuntu-latest`
- **Steps:**
  1. Checkout repo
  2. Set up Python 3.12
  3. Install dependencies from `requirements.txt`
  4. Download previous `state.json` from GitHub Actions cache (or start fresh if none exists)
  5. Run `python bots/claude_bot/main.py`
  6. Upload updated `state.json` to cache

State is persisted via GitHub Actions cache rather than committing to the repo, keeping the repo clean.

### Environment Variables

```yaml
env:
  TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
  TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
```

## Error Handling & Edge Cases

- **Status page unreachable:** Log a warning, skip the run. If unreachable for 3+ consecutive runs (tracked via `consecutive_failures` in state), send a single warning to Telegram.
- **Telegram API failure:** Log the error, exit with non-zero code so GitHub Actions marks the run as failed (visible in Actions tab).
- **First run (no previous state):** Load current incidents into state without sending notifications. Prevents a flood of messages about existing incidents on first deploy.
- **Duplicate notifications:** The `last_update_id` comparison ensures the same update is never sent twice, even if the cron overlaps.

## Technology Stack

- **Language:** Python 3.12
- **Dependencies:** `requests` (HTTP), standard library only otherwise
- **Deployment:** GitHub Actions scheduled workflows
- **Notifications:** Telegram Bot API
- **State persistence:** GitHub Actions cache

## Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Architecture | Simple script per bot | Right-sized for current scope; refactor to base class when 3+ bots exist |
| Polling interval | 15 minutes | Lightweight, sufficient for status page monitoring |
| State storage | GitHub Actions cache | Keeps repo clean, no noisy commits |
| Notification scope | Full lifecycle | New + updates + resolved for complete visibility |
| Language | Python | Simple, good libraries, team familiarity |
