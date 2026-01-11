# 🐦 Twitter/X Alpha Account Monitor

A Python-based monitoring system that tracks "New Follows" from specific Twitter/X accounts (Alpha accounts) and sends real-time alerts to Discord. Built to bypass expensive API costs using the `twscrape` library.

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Status](https://img.shields.io/badge/Status-Development-yellow.svg)

## 🎯 Features

- **Real-time Follow Monitoring** - Track when Alpha accounts follow new users
- **High-Water Mark Algorithm** - Efficient polling that only fetches new follows
- **Discord Webhook Integration** - Instant alerts with rich embeds
- **Account Pool Management** - Rotate between multiple worker accounts
- **Anti-Detection** - Random jitter, stealth mode, proxy support
- **VPS Ready** - Designed to run 24/7 on any VPS

## 🛠️ Tech Stack

- **twscrape** - GraphQL-based Twitter scraping
- **Playwright** - Browser automation for stealth login
- **discord-webhook** - Discord alert integration
- **loguru** - Advanced logging
- **curl_cffi** - TLS fingerprint evasion

## 📁 Project Structure

```
tw_alpha_scraper/
├── config.json           # Configuration (webhook URL, targets, poll interval)
├── setup.py              # Account management CLI (add/login accounts)
├── manual_add.py         # Add account with pre-obtained cookies
├── monitor.py            # Main monitoring script
├── vps_login_stealth.py  # Playwright-based stealth login for VPS
├── local_login.py        # Local browser login via proxy
├── accounts.db           # SQLite database for account pool
├── state.json            # High-water mark state persistence
└── requirements.txt      # Python dependencies
```

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure Targets
Edit `config.json`:
```json
{
    "discord_webhook_url": "https://discord.com/api/webhooks/...",
    "poll_interval": 300,
    "targets": ["44196397"]  // Twitter User IDs to monitor
}
```

### 3. Add Worker Account
```bash
python setup.py add      # Add account with proxy
python setup.py login    # Login to generate cookies
```

### 4. Start Monitoring
```bash
python monitor.py
```

## ⚠️ Known Challenges & Limitations

### 🔴 Cloudflare Blocking
- **Issue:** Twitter uses aggressive Cloudflare protection that blocks most VPS/datacenter IPs
- **Impact:** Standard `twscrape` login fails with 403 errors
- **Workaround:** Use residential proxies or cookie injection

### 🔴 Proxy Quality
- **Issue:** Many "residential proxy" providers are actually flagged datacenter IPs
- **Impact:** Even with proxy, Twitter blocks login attempts with "Could not log you in now"
- **Tested:** Webshare Static Residential - BLOCKED by Twitter
- **Recommendation:** Use premium providers (Bright Data, IPRoyal, Oxylabs)

### 🔴 Session/Cookie Validation
- **Issue:** Twitter validates cookies against IP geolocation
- **Impact:** Cookies obtained from IP-A fail when used from IP-B
- **Workaround:** Generate cookies through the same proxy that will be used for scraping

### 🔴 Account Verification
- **Issue:** Twitter requires phone verification for new IP logins
- **Impact:** Accounts without phone numbers cannot complete login
- **Workaround:** Add phone number to Twitter account before using

### 🟡 API Changes
- **Issue:** Twitter frequently changes their GraphQL API structure
- **Impact:** `twscrape` may break with "Failed to parse scripts" error
- **Workaround:** Monkey patch in `monitor.py` (see GitHub issues)

## 🔧 Alternative Approaches

If the above methods fail, consider:

1. **Premium Residential Proxies** - Higher cost but more reliable
2. **Mobile Proxies** - Rarely blocked but expensive
3. **Manual Cookie Injection** - Login manually, export cookies
4. **VNC on VPS** - Run a GUI browser on VPS via VNC
5. **Official Twitter API** - Most reliable but costs $100+/month

## 📊 High-Water Mark Algorithm

```
1. Store last_seen_follow_id for each target
2. Fetch following list (newest first)
3. Stop when last_seen_follow_id is encountered
4. Everything above is a NEW follow
5. Update last_seen_follow_id
6. Send Discord alerts for new follows
```

This approach minimizes API calls and avoids comparing full follower lists.

## 🤝 Contributing

PRs welcome! Areas that need work:
- Better Cloudflare bypass
- Support for more proxy providers
- Improved error handling

## 📝 License

MIT License - Use at your own risk. Twitter scraping may violate ToS.

---

**Note:** This is an educational project demonstrating web scraping techniques. Always respect rate limits and Terms of Service.
