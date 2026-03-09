# tw_alpha_scraper

`tw_alpha_scraper` is a Discord-first Twitter/X follow monitor for private alpha tracking. It watches the accounts that a target user follows, stores every unique follow event in SQLite, and pushes alerts to Discord. A small Discord admin bot manages targets and runtime state on a single VPS.

## What Changed

- Core logic now lives in the `tw_alpha_scraper/` package instead of ad hoc scripts.
- Persistence moved from `state.json` to SQLite for targets, follow events, monitor state, worker health, and admin audit logs.
- Runtime is one asyncio service with:
  - monitor loop
  - Discord slash-command admin bot
  - Discord webhook alerts
- Legacy scripts remain as wrappers so old workflows still work while pointing to the new app.

## Architecture

- `config.py`: loads nested `config.json` plus secret overrides from `.env`
- `storage.py`: SQLite schema and persistence helpers
- `service.py`: monitor scheduler, bootstrap logic, dedupe, retries, and admin actions
- `bot.py`: Discord slash commands for `/status`, `/targets list`, `/targets add`, `/targets remove`, `/pause`, `/resume`
- `twitter.py`: `twscrape` integration and worker account access
- `accounts.py`: interactive worker account management

## Setup

### 1. Install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### 2. Create config files

```bash
cp config.example.json config.json
cp .env.example .env
```

Update:

- `config.json` for non-secret runtime settings and initial targets
- `.env` for Discord webhook, Discord bot token, and any local overrides

### 3. Provision worker accounts

Interactive account management:

```bash
python -m tw_alpha_scraper accounts add
python -m tw_alpha_scraper accounts login
python -m tw_alpha_scraper accounts list
```

Manual cookie injection:

```bash
python -m tw_alpha_scraper accounts manual-add
```

Helper scripts are still available:

```bash
python local_login.py
python vps_login_stealth.py
python setup.py add
python setup.py login
```

## Runtime Commands

Initialize the app DB:

```bash
python -m tw_alpha_scraper init-db
```

Import old `state.json` data:

```bash
python -m tw_alpha_scraper migrate-state
```

Check worker and service health:

```bash
python -m tw_alpha_scraper health-check
```

Sync one target once:

```bash
python -m tw_alpha_scraper sync-target 44196397
python -m tw_alpha_scraper sync-target @example --send-alerts
```

Run the full service:

```bash
python -m tw_alpha_scraper run
```

Run monitor only, without the admin bot:

```bash
python -m tw_alpha_scraper run --without-bot
```

## Discord Commands

- `/status`
- `/targets list`
- `/targets add`
- `/targets remove`
- `/pause`
- `/resume`

Access is controlled by `discord.admin_channel_id` and/or `discord.admin_role_ids`. If neither is set, the bot falls back to users with the `Manage Guild` permission.

## Data Model

The app SQLite database contains:

- `targets`
- `monitor_state`
- `follow_events`
- `worker_health`
- `admin_actions`

`accounts.db` remains owned by `twscrape` and is not replaced.

## Monitor Behavior

- First sync for a target bootstraps the latest known follow and does not spam the backlog.
- New alerts are deduped by `(target_user_id, followed_user_id)` at the database layer.
- Polling uses bounded retries, timeout protection, and small jitter between targets.
- Worker pool health is exposed via `health-check` and `/status`.

## Deploy on Ubuntu VPS

1. Clone the repo to a fixed path such as `/opt/tw_alpha_scraper`.
2. Create `.venv`, install requirements, and install Playwright Chromium.
3. Create `config.json` and `.env`.
4. Add worker accounts manually.
5. Copy `deploy/systemd/tw_alpha_scraper.service` and update the absolute paths.
6. Enable the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now tw_alpha_scraper
sudo systemctl status tw_alpha_scraper
```

## Testing

```bash
pytest -q
```

The automated tests cover config loading, access policy, database dedupe, bootstrap/no-backlog behavior, and retry recovery with fake Twitter/Discord integrations.
