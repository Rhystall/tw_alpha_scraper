from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any
from urllib import request

from .models import ResolvedUser, TargetRecord


class DiscordWebhookNotifier:
    def __init__(self, webhook_url: str | None, logger: logging.Logger):
        self.webhook_url = webhook_url
        self.logger = logger

    async def send_follow_alert(self, target: TargetRecord, followed_user: ResolvedUser) -> bool:
        if not self.webhook_url:
            self.logger.warning("Discord webhook is not configured; skipping alert delivery.")
            return False

        embed: dict[str, Any] = {
            "title": f"New follow detected: {target.display_label()}",
            "description": (
                f"**{followed_user.display_name or followed_user.username or followed_user.id}** "
                f"(@{followed_user.username or 'unknown'})"
            ),
            "color": 0x03B2F8,
            "fields": [
                {
                    "name": "Target",
                    "value": (
                        f"{target.display_label()}\n"
                        f"`{target.user_id}`"
                    ),
                    "inline": True,
                },
                {
                    "name": "Profile",
                    "value": f"https://x.com/{followed_user.username}" if followed_user.username else "Unknown",
                    "inline": True,
                },
                {
                    "name": "Bio",
                    "value": followed_user.description or "No bio available.",
                    "inline": False,
                },
            ],
            "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        }
        if followed_user.profile_image_url:
            embed["thumbnail"] = {"url": followed_user.profile_image_url}

        payload = {"embeds": [embed]}
        await asyncio.to_thread(self._post_payload, payload)
        return True

    def _post_payload(self, payload: dict[str, Any]) -> None:
        data = json.dumps(payload).encode("utf-8")
        req = request.Request(
            self.webhook_url,
            data=data,
            headers={"Content-Type": "application/json", "User-Agent": "tw_alpha_scraper (https://github.com, 1.0)"},
            method="POST",
        )
        with request.urlopen(req, timeout=15) as response:
            if response.status >= 400:
                raise RuntimeError(f"Discord webhook returned HTTP {response.status}")
