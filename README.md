# 🐦 tw_alpha_scraper

`tw_alpha_scraper` is a Discord-first Twitter/X follow monitor for private alpha tracking. It watches the accounts that a target user (e.g., influencers, founders) follows, stores every unique follow event in an SQLite database, and pushes real-time alerts to a Discord webhook. A built-in Discord admin bot manages targets and runtime state directly from your server.

## 🌟 Features

- **Real-time Follow Monitoring**: Track when target accounts follow new users.
- **Discord Bot Management**: Use Slash Commands (`/status`, `/targets add`) directly in Discord.
- **Discord Webhook Alerts**: Instant notifications with rich embeds and anti-403 User-Agent protections.
- **Resilient Polling**: Built-in retry logic, timeout protection, and jitter to avoid rate limits.
- **Cookie Injection**: Bypass Twitter/Cloudflare VPS login blocks via local cookie injection.
- **SQLite Persistence**: Robust data tracking for targets, events, and worker health.
- **Production Ready**: Includes `systemd` service configuration for 24/7 VPS deployment.

---

## 🛠️ 1. Discord Bot Setup (CRITICAL)

Before running the scraper, you must create a Discord Bot and configure it correctly:

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications) and create a New Application.
2. Go to the **Bot** tab, copy the **Token**.
3. **Turn on Intents**: Scroll down to *Privileged Gateway Intents* and enable **Message Content Intent**, **Presence Intent**, and **Server Members Intent**. Save changes.
4. Go to the **OAuth2 > General** tab, and **Disable** "Require OAuth2 Code Grant".
5. Go to **OAuth2 > URL Generator**:
   - Scopes: Select `bot` AND `applications.commands`.
   - Bot Permissions: Select `Send Messages`, `Embed Links`, `Read Messages/View Channels`.
6. Copy the generated URL at the bottom, paste it into your browser, and authorize the bot to your server.
7. Get your **Guild ID** (Server ID): Enable Developer Mode in Discord settings, right-click your Server icon, and click "Copy Server ID".

---

## 🚀 2. Installation

Clone the repository and install the dependencies (Python 3.10+ required):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

*(Note for Ubuntu VPS: Ensure you have installed `python3-venv` and system dependencies if Playwright prompts for them via `playwright install-deps`).*

---

## ⚙️ 3. Configuration

Copy the example configuration files:

```bash
cp config.example.json config.json
cp .env.example .env
```

**Edit `.env`** with your credentials:
```env
DISCORD_ALERT_WEBHOOK_URL=https://discord.com/api/webhooks/...
DISCORD_BOT_TOKEN=your-bot-token-here
DISCORD_GUILD_ID=123456789012345678  # Your Server ID (NOT the webhook ID)
DISCORD_ADMIN_CHANNEL_ID=0           # Optional: Restrict commands to specific channel
```

**Edit `config.json`** for runtime settings and initial targets.

---

## 🔑 4. Adding a Twitter Worker Account

Because Twitter aggressively blocks automated logins from Datacenter/VPS IPs, the most reliable method is to grab cookies from your local browser and inject them into the VPS.

**Step A: Get Cookies (Local Machine)**
1. Run `python local_login.py` on your local PC.
2. A browser will open. Log in to your burner Twitter account manually.
3. Once on the homepage, press `Enter` in the terminal. It will output your `auth_token` and `ct0` cookies.

**Step B: Inject Cookies (VPS / Server)**
Run the manual addition script and paste the cookie string when prompted:
```bash
python -m tw_alpha_scraper accounts manual-add
```
Verify the account is active:
```bash
python -m tw_alpha_scraper accounts list
```

---

## 🗄️ 5. Initialize & Test

Initialize the SQLite database and seed initial targets:
```bash
python -m tw_alpha_scraper init-db
```

Test a single synchronization without sending Discord alerts (bootstraps the database):
```bash
python -m tw_alpha_scraper sync-target @elonmusk
```

Force a sync and test the Discord Webhook alert:
```bash
python -m tw_alpha_scraper sync-target @elonmusk --send-alerts
```

---

## 🖥️ 6. Production Deployment (systemd)

To run the monitor and Discord bot 24/7 on an Ubuntu VPS:

1. Ensure the project is located at `/opt/tw_alpha_scraper`.
2. Copy the service file to systemd:
   ```bash
   sudo cp deploy/systemd/tw_alpha_scraper.service /etc/systemd/system/
   ```
3. Reload systemd and start the service:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now tw_alpha_scraper
   ```
4. Check the status:
   ```bash
   sudo systemctl status tw_alpha_scraper
   ```
5. View logs:
   ```bash
   sudo journalctl -u tw_alpha_scraper -f
   ```

---

## 🤖 Discord Slash Commands

Once the bot is online, you can manage the scraper directly from Discord:

- `/status` - View current health, active targets, and last sync time.
- `/targets list` - List all tracked accounts.
- `/targets add <username>` - Add a new Twitter account to track.
- `/targets remove <username>` - Stop tracking an account.
- `/pause` - Pause the monitoring loop.
- `/resume` - Resume the monitoring loop.

*(Note: Target checking is subject to Twitter's rate limits. The scraper enforces a cooldown to protect your worker accounts).*
