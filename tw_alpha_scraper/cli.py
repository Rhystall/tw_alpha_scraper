from __future__ import annotations

import argparse
import asyncio
import json
import signal
from dataclasses import asdict
from pathlib import Path
from typing import Sequence

from .accounts import run_account_command_sync
from .bot import DiscordAdminBot
from .config import load_config
from .logging_utils import setup_logging
from .service import AlphaMonitorService
from .storage import AppDatabase


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Discord-first Twitter alpha monitor")
    parser.add_argument("--config", default=None, help="Path to config.json")
    parser.add_argument("--env-file", default=None, help="Path to .env file")

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init-db", help="Initialize the application SQLite database.")
    subparsers.add_parser("health-check", help="Check worker and service health.")

    migrate_parser = subparsers.add_parser("migrate-state", help="Import legacy state.json into the app DB.")
    migrate_parser.add_argument("--state-file", default=None, help="Legacy state.json path")

    sync_parser = subparsers.add_parser("sync-target", help="Synchronize a single target once.")
    sync_parser.add_argument("identifier", help="Target user ID, username, or label")
    sync_parser.add_argument(
        "--send-alerts",
        action="store_true",
        help="Deliver Discord alerts for newly found follows.",
    )

    run_parser = subparsers.add_parser("run", help="Run monitor loop and Discord admin bot.")
    run_parser.add_argument(
        "--without-bot",
        action="store_true",
        help="Run the monitor loop without starting the Discord bot.",
    )

    accounts_parser = subparsers.add_parser("accounts", help="Manage twscrape worker accounts.")
    accounts_subparsers = accounts_parser.add_subparsers(dest="account_command", required=True)
    accounts_subparsers.add_parser("add", help="Interactively add an account.")
    accounts_subparsers.add_parser("manual-add", help="Add an account with cookie injection.")
    accounts_subparsers.add_parser("login", help="Run twscrape login for all accounts.")
    accounts_subparsers.add_parser("list", help="List accounts in the twscrape pool.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "accounts":
        return run_account_command_sync(args.account_command)

    config = load_config(config_path=args.config, env_path=args.env_file)
    logger = setup_logging(config.storage.log_file_path)
    storage = AppDatabase(config.storage.app_db_path)
    service = AlphaMonitorService(config=config, storage=storage, logger=logger)

    try:
        if args.command == "init-db":
            service.storage.initialize()
            service.storage.seed_targets(config.targets)
            print(f"Initialized database at {config.storage.app_db_path}")
            return 0
        if args.command == "migrate-state":
            return asyncio.run(_migrate_state(service, args.state_file or config.storage.legacy_state_path))
        if args.command == "health-check":
            return asyncio.run(_health_check(service))
        if args.command == "sync-target":
            return asyncio.run(_sync_target(service, args.identifier, args.send_alerts))
        if args.command == "run":
            return asyncio.run(_run_service(service, include_bot=not args.without_bot))
    finally:
        storage.close()

    parser.error(f"Unknown command: {args.command}")
    return 1


async def _migrate_state(service: AlphaMonitorService, state_file: str) -> int:
    await service.initialize()
    path = Path(state_file)
    if not path.exists():
        print(f"Legacy state file not found: {state_file}")
        return 1

    payload = json.loads(path.read_text())
    for user_id, last_seen in payload.items():
        if not service.storage.get_target(str(user_id)):
            service.storage.upsert_target(str(user_id), active=True)
        service.storage.set_target_last_seen(str(user_id), str(last_seen))

    print(f"Migrated {len(payload)} legacy state entries from {state_file}")
    return 0


async def _health_check(service: AlphaMonitorService) -> int:
    await service.initialize()
    status = await service.health_check()
    print(json.dumps(status, indent=2))
    return 0


async def _sync_target(service: AlphaMonitorService, identifier: str, send_alerts: bool) -> int:
    await service.initialize()
    result = await service.sync_target(identifier, send_alerts=send_alerts)
    print(json.dumps(asdict(result), indent=2, default=str))
    return 0


async def _run_service(service: AlphaMonitorService, include_bot: bool) -> int:
    await service.initialize()
    monitor_task = asyncio.create_task(service.run_forever(), name="monitor-loop")
    bot: DiscordAdminBot | None = None
    tasks = [monitor_task]

    if include_bot and service.config.discord.bot_token:
        bot = DiscordAdminBot(service)
        tasks.append(asyncio.create_task(bot.start(), name="discord-bot"))

    stop_event = asyncio.Event()

    def _signal_handler(*_: object) -> None:
        stop_event.set()

    loop = asyncio.get_running_loop()
    for signame in ("SIGINT", "SIGTERM"):
        if hasattr(signal, signame):
            loop.add_signal_handler(getattr(signal, signame), _signal_handler)

    waiter = asyncio.create_task(stop_event.wait(), name="shutdown-waiter")
    done, pending = await asyncio.wait(tasks + [waiter], return_when=asyncio.FIRST_COMPLETED)

    if waiter in done:
        await service.shutdown()
        monitor_task.cancel()
        if bot:
            await bot.close()
    else:
        for task in done:
            task.result()
        waiter.cancel()

    for task in pending:
        task.cancel()
    await asyncio.gather(*pending, return_exceptions=True)
    return 0
