from __future__ import annotations

import json
import re
from typing import Any

from .models import ResolvedUser


class TwitterClientError(RuntimeError):
    """Raised when the Twitter client cannot complete a request."""


class TwitterClient:
    def __init__(self) -> None:
        self._api: Any | None = None

    def _ensure_api(self) -> Any:
        if self._api is not None:
            return self._api

        self._apply_script_patch()
        try:
            from twscrape import API
        except Exception as exc:
            raise TwitterClientError(f"Failed to load twscrape: {exc}") from exc

        self._api = API()
        return self._api

    def _apply_script_patch(self) -> None:
        try:
            from twscrape import xclid
        except (ImportError, ModuleNotFoundError):
            return

        if getattr(xclid, "_tw_alpha_scraper_patched", False):
            return

        def script_url(key: str, value: str) -> str:
            return f"https://abs.twimg.com/responsive-web/client-web/{key}.{value}.js"

        def patched_get_scripts_list(text: str):
            try:
                scripts = text.split('e=>e+"."+')[1].split('[e]+"a.js"')[0]
            except IndexError:
                return

            try:
                for key, value in json.loads(scripts).items():
                    yield script_url(key, f"{value}a")
            except json.decoder.JSONDecodeError:
                fixed_scripts = re.sub(
                    r'([,\{])(\s*)([a-zA-Z_][a-zA-Z0-9_]*)(\s*):',
                    r'\1\2"\3"\4:',
                    scripts,
                )
                for key, value in json.loads(fixed_scripts).items():
                    yield script_url(key, f"{value}a")

        xclid.get_scripts_list = patched_get_scripts_list
        xclid._tw_alpha_scraper_patched = True

    async def resolve_user(self, identifier: str) -> ResolvedUser:
        api = self._ensure_api()
        if identifier.isdigit():
            raw_user = await api.user_by_id(int(identifier))
            if not raw_user:
                raise TwitterClientError(f"Twitter user `{identifier}` was not found.")
            return self._to_user(raw_user)

        username = identifier.lstrip("@")
        for method_name in ("user_by_login", "user_by_username", "user_by_screen_name"):
            method = getattr(api, method_name, None)
            if method is None:
                continue
            raw_user = await method(username)
            if raw_user:
                return self._to_user(raw_user)

        raise TwitterClientError(
            "The current twscrape version cannot resolve usernames directly. Use numeric user_id instead."
        )

    async def iter_following(self, user_id: str, limit: int | None = None):
        api = self._ensure_api()
        count = 0
        async for raw_user in api.following(int(user_id)):
            yield self._to_user(raw_user)
            count += 1
            if limit is not None and count >= limit:
                break

    async def list_accounts(self) -> list[dict[str, Any]]:
        api = self._ensure_api()
        accounts = await api.pool.accounts_info()
        normalized: list[dict[str, Any]] = []
        for account in accounts:
            if isinstance(account, dict):
                normalized.append(account)
                continue

            normalized.append(
                {
                    "username": getattr(account, "username", None),
                    "active": getattr(account, "active", False),
                    "proxy": getattr(account, "proxy", None),
                    "last_error": getattr(account, "error_msg", None),
                }
            )
        return normalized

    async def add_account(
        self,
        *,
        username: str,
        password: str,
        email: str,
        email_password: str,
        cookies: str | None = None,
        proxy: str | None = None,
    ) -> None:
        api = self._ensure_api()
        payload: dict[str, Any] = {
            "username": username,
            "password": password,
            "email": email,
            "email_password": email_password,
        }
        if cookies:
            payload["cookies"] = cookies
        if proxy:
            payload["proxy"] = proxy
        await api.pool.add_account(**payload)

    async def delete_accounts(self, usernames: list[str]) -> None:
        api = self._ensure_api()
        await api.pool.delete_accounts(usernames)

    async def login_all(self) -> None:
        api = self._ensure_api()
        await api.pool.login_all()

    @staticmethod
    def _to_user(raw_user: Any) -> ResolvedUser:
        return ResolvedUser(
            id=str(getattr(raw_user, "id", "")),
            username=getattr(raw_user, "username", None),
            display_name=getattr(raw_user, "name", None),
            description=getattr(raw_user, "description", None),
            profile_image_url=getattr(raw_user, "profile_image_url", None),
            raw=raw_user,
        )
