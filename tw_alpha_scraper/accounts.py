from __future__ import annotations

import asyncio
from getpass import getpass
from typing import Any

from .twitter import TwitterClient, TwitterClientError


def parse_cookie_string(cookie_string: str) -> str:
    cookies: dict[str, str] = {}
    for part in cookie_string.split(";"):
        fragment = part.strip()
        if "=" not in fragment:
            continue
        key, value = fragment.split("=", 1)
        cookies[key.strip()] = value.strip()

    if "auth_token" not in cookies or "ct0" not in cookies:
        raise ValueError("Cookie string must contain both auth_token and ct0.")
    return cookie_string.strip()


async def add_account_interactive(client: TwitterClient) -> str:
    username = input("Twitter username (without @): ").strip()
    password = getpass("Twitter password: ").strip()
    email = input("Email: ").strip()
    email_password = getpass("Email password: ").strip()
    proxy = input("Proxy (http://user:pass@host:port) [optional]: ").strip() or None

    try:
        await client.delete_accounts([username])
    except Exception:
        pass

    await client.add_account(
        username=username,
        password=password,
        email=email,
        email_password=email_password,
        proxy=proxy,
    )
    return f"Account `{username}` added. Run `python -m tw_alpha_scraper accounts login` next."


async def manual_add_account_interactive(client: TwitterClient) -> str:
    username = input("Twitter username (without @): ").strip()
    password = getpass("Twitter password: ").strip()
    email = input("Email: ").strip()
    email_password = getpass("Email password: ").strip()
    cookie_string = input("Cookie string (auth_token=...; ct0=...): ").strip()
    proxy = input("Proxy (http://user:pass@host:port) [optional]: ").strip() or None

    parsed_cookies = parse_cookie_string(cookie_string)
    try:
        await client.delete_accounts([username])
    except Exception:
        pass

    await client.add_account(
        username=username,
        password=password,
        email=email,
        email_password=email_password,
        cookies=parsed_cookies,
        proxy=proxy,
    )
    return f"Account `{username}` added with injected cookies."


async def login_accounts_interactive(client: TwitterClient) -> str:
    await client.login_all()
    return "Login flow completed. Check monitor logs for any account failures."


async def list_accounts_interactive(client: TwitterClient) -> str:
    accounts = await client.list_accounts()
    if not accounts:
        return "No worker accounts configured."

    lines = ["Configured worker accounts:"]
    for account in accounts:
        username = account.get("username", "unknown")
        active = "active" if account.get("active") else "inactive"
        proxy = account.get("proxy") or "no proxy"
        lines.append(f"- {username}: {active}, proxy={proxy}")
    return "\n".join(lines)


async def run_account_command(action: str) -> int:
    client = TwitterClient()
    handlers: dict[str, Any] = {
        "add": add_account_interactive,
        "manual-add": manual_add_account_interactive,
        "login": login_accounts_interactive,
        "list": list_accounts_interactive,
    }
    handler = handlers.get(action)
    if handler is None:
        raise SystemExit(f"Unknown account action: {action}")

    try:
        message = await handler(client)
    except (TwitterClientError, ValueError) as exc:
        print(f"Error: {exc}")
        return 1

    print(message)
    return 0


def run_account_command_sync(action: str) -> int:
    return asyncio.run(run_account_command(action))
