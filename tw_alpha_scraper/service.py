from __future__ import annotations

import asyncio
import json
import logging
import random
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from .models import AdminActor, AppConfig, CommandResult, FollowEvent, ResolvedUser, SyncResult, TargetRecord
from .notifications import DiscordWebhookNotifier
from .storage import AppDatabase, utcnow_iso
from .twitter import TwitterClient, TwitterClientError


def compute_backoff_seconds(attempt: int, base_delay_seconds: float) -> float:
    return base_delay_seconds * (2 ** max(attempt - 1, 0))


class AlphaMonitorService:
    def __init__(
        self,
        config: AppConfig,
        storage: AppDatabase,
        twitter_client: TwitterClient | None = None,
        notifier: DiscordWebhookNotifier | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.config = config
        self.storage = storage
        self.twitter = twitter_client or TwitterClient()
        self.logger = logger or logging.getLogger("tw_alpha_scraper")
        self.notifier = notifier or DiscordWebhookNotifier(config.discord.alert_webhook_url, self.logger)
        self.started_at = utcnow_iso()
        self.last_cycle_at: str | None = None
        self.last_runtime_error: str | None = None
        self.degraded = False
        self._stop_event = asyncio.Event()
        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            return
        self.storage.initialize()
        self.storage.seed_targets(self.config.targets)
        if self.storage.get_state("paused", None) is None:
            self.storage.set_paused(self.config.monitor.pause_on_start)
        self.storage.set_state("started_at", self.started_at)
        await self.refresh_worker_health()
        self._initialized = True

    async def run_forever(self) -> None:
        self.logger.info("Service initialized with %s active targets.", len(self.storage.list_targets(active_only=True)))
        while not self._stop_event.is_set():
            if self.storage.is_paused():
                await asyncio.sleep(self.config.monitor.scheduler_tick_seconds)
                continue

            await self.run_monitor_cycle()
            await asyncio.sleep(self.config.monitor.scheduler_tick_seconds)

    async def shutdown(self) -> None:
        self._stop_event.set()

    async def run_monitor_cycle(self) -> None:
        targets = self.storage.list_targets(active_only=True)
        cycle_started = utcnow_iso()
        self.last_cycle_at = cycle_started
        self.storage.set_state("last_cycle_at", cycle_started)
        for target in targets:
            if self._stop_event.is_set():
                break
            if not self._target_due(target):
                continue
            try:
                await self.sync_target(target.user_id, send_alerts=True)
            except Exception as exc:
                self.last_runtime_error = str(exc)
                self.storage.set_state("last_runtime_error", self.last_runtime_error)
                self.storage.set_target_poll_failure(target.user_id, str(exc))
                self.logger.exception("Target sync failed for %s", target.user_id)
            await asyncio.sleep(
                random.uniform(
                    self.config.monitor.target_jitter_min_seconds,
                    self.config.monitor.target_jitter_max_seconds,
                )
            )

    def _target_due(self, target: TargetRecord) -> bool:
        if not target.last_polled_at:
            return True
        last_polled = datetime.fromisoformat(target.last_polled_at)
        due_after = last_polled.timestamp() + target.poll_interval(self.config.monitor.default_poll_interval_seconds)
        return datetime.now(timezone.utc).timestamp() >= due_after

    async def sync_target(self, identifier: str, send_alerts: bool = False) -> SyncResult:
        target = self.storage.get_target(identifier)
        if target is None:
            raise ValueError(f"Target `{identifier}` is not configured.")

        observed_at = datetime.now(timezone.utc)
        fetched_users = await self._run_with_retries(
            lambda: self._fetch_following_snapshot(target.user_id),
            operation_name=f"fetch following for {target.user_id}",
        )

        current_head = fetched_users[0] if fetched_users else None
        if target.last_seen_followed_user_id is None:
            self.storage.set_target_poll_success(
                target.user_id,
                current_head.id if current_head else None,
                username=target.username,
                display_name=target.display_name,
            )
            return SyncResult(
                target_user_id=target.user_id,
                target_label=target.display_label(),
                bootstrapped=True,
                fetched_count=len(fetched_users),
                inserted_count=0,
                notified_count=0,
                last_seen_followed_user_id=current_head.id if current_head else None,
                observed_at=observed_at,
            )

        new_users: list[ResolvedUser] = []
        for followed_user in fetched_users:
            if followed_user.id == target.last_seen_followed_user_id:
                break
            new_users.append(followed_user)

        inserted_count = 0
        notified_count = 0
        for followed_user in reversed(new_users):
            event_id = self.storage.record_follow_event(
                FollowEvent(
                    target_user_id=target.user_id,
                    target_username=target.username,
                    target_display_name=target.display_label(),
                    followed_user_id=followed_user.id,
                    followed_username=followed_user.username,
                    followed_display_name=followed_user.display_name,
                    followed_bio=followed_user.description,
                    followed_profile_image_url=followed_user.profile_image_url,
                    observed_at=observed_at.replace(microsecond=0).isoformat(),
                    payload_json=json.dumps(
                        {
                            "target_user_id": target.user_id,
                            "followed_user_id": followed_user.id,
                            "followed_username": followed_user.username,
                        }
                    ),
                )
            )
            if not event_id:
                continue
            inserted_count += 1
            if send_alerts:
                delivered = await self.notifier.send_follow_alert(target, followed_user)
                if delivered:
                    self.storage.mark_event_notified(event_id)
                    notified_count += 1

        self.storage.set_target_poll_success(
            target.user_id,
            current_head.id if current_head else target.last_seen_followed_user_id,
            username=target.username,
            display_name=target.display_name,
        )
        self.last_runtime_error = None
        self.degraded = False
        return SyncResult(
            target_user_id=target.user_id,
            target_label=target.display_label(),
            bootstrapped=False,
            fetched_count=len(fetched_users),
            inserted_count=inserted_count,
            notified_count=notified_count,
            last_seen_followed_user_id=current_head.id if current_head else target.last_seen_followed_user_id,
            observed_at=observed_at,
        )

    async def add_target(
        self,
        identifier: str,
        label: str | None = None,
        poll_interval_seconds: int | None = None,
        actor: AdminActor | None = None,
    ) -> CommandResult:
        resolved = await self._run_with_retries(
            lambda: self.twitter.resolve_user(identifier),
            operation_name=f"resolve target {identifier}",
        )
        self.storage.upsert_target(
            user_id=resolved.id,
            username=resolved.username,
            display_name=resolved.display_name,
            label=label,
            poll_interval_seconds=poll_interval_seconds,
            active=True,
        )
        result = await self.sync_target(resolved.id, send_alerts=False)
        if actor:
            self.storage.record_admin_action(
                actor.actor_id,
                actor.actor_name,
                "targets.add",
                {
                    "identifier": identifier,
                    "resolved_user_id": resolved.id,
                    "label": label,
                    "poll_interval_seconds": poll_interval_seconds,
                },
            )
        return CommandResult(
            ok=True,
            message=(
                f"Target `{resolved.id}` added as `{resolved.username or resolved.display_name or resolved.id}`. "
                "Bootstrap completed without sending historical alerts."
            ),
            payload={"sync_result": asdict(result)},
        )

    async def remove_target(self, identifier: str, actor: AdminActor | None = None) -> CommandResult:
        removed = self.storage.deactivate_target(identifier)
        if not removed:
            return CommandResult(ok=False, message=f"Target `{identifier}` was not found.")
        if actor:
            self.storage.record_admin_action(
                actor.actor_id,
                actor.actor_name,
                "targets.remove",
                {"identifier": identifier},
            )
        return CommandResult(ok=True, message=f"Target `{identifier}` deactivated.")

    async def pause(self, actor: AdminActor | None = None) -> CommandResult:
        self.storage.set_paused(True)
        if actor:
            self.storage.record_admin_action(actor.actor_id, actor.actor_name, "monitor.pause", {})
        return CommandResult(ok=True, message="Monitor paused.")

    async def resume(self, actor: AdminActor | None = None) -> CommandResult:
        self.storage.set_paused(False)
        if actor:
            self.storage.record_admin_action(actor.actor_id, actor.actor_name, "monitor.resume", {})
        return CommandResult(ok=True, message="Monitor resumed.")

    async def refresh_worker_health(self) -> None:
        try:
            accounts = await self.twitter.list_accounts()
        except TwitterClientError as exc:
            self.degraded = True
            self.last_runtime_error = str(exc)
            self.storage.set_state("last_runtime_error", self.last_runtime_error)
            return

        for account in accounts:
            self.storage.upsert_worker_health(account)
        self.degraded = not any(account.get("active") for account in accounts) if accounts else True

    async def health_check(self) -> dict[str, Any]:
        await self.refresh_worker_health()
        snapshot = self.storage.build_runtime_snapshot(
            started_at=self.started_at,
            paused=self.storage.is_paused(),
            degraded=self.degraded,
            last_cycle_at=self.last_cycle_at or self.storage.get_state("last_cycle_at"),
            last_alert_at=self.storage.get_state("last_alert_at"),
            last_runtime_error=self.last_runtime_error or self.storage.get_state("last_runtime_error"),
        )
        return asdict(snapshot)

    async def status_text(self) -> str:
        snapshot = await self.health_check()
        lines = [
            f"paused: {snapshot['paused']}",
            f"degraded: {snapshot['degraded']}",
            f"started_at: {snapshot['started_at']}",
            f"last_cycle_at: {snapshot['last_cycle_at']}",
            f"last_alert_at: {snapshot['last_alert_at']}",
            f"active_targets: {snapshot['active_targets']}",
            f"healthy_workers: {snapshot['healthy_workers']}/{snapshot['total_workers']}",
            f"last_runtime_error: {snapshot['last_runtime_error']}",
        ]
        return "\n".join(lines)

    async def _fetch_following_snapshot(self, user_id: str) -> list[ResolvedUser]:
        async def _collect() -> list[ResolvedUser]:
            results: list[ResolvedUser] = []
            async for user in self.twitter.iter_following(
                user_id,
                limit=self.config.monitor.max_follow_scan,
            ):
                results.append(user)
            return results

        return await asyncio.wait_for(
            _collect(),
            timeout=self.config.monitor.api_timeout_seconds,
        )

    async def _run_with_retries(
        self,
        action: Callable[[], Awaitable[Any]],
        *,
        operation_name: str,
    ) -> Any:
        last_error: Exception | None = None
        for attempt in range(1, self.config.monitor.max_retry_attempts + 1):
            try:
                return await action()
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt >= self.config.monitor.max_retry_attempts:
                    break
                delay = compute_backoff_seconds(
                    attempt,
                    self.config.monitor.retry_base_delay_seconds,
                )
                self.logger.warning(
                    "Retrying %s after failure on attempt %s/%s: %s",
                    operation_name,
                    attempt,
                    self.config.monitor.max_retry_attempts,
                    exc,
                )
                await asyncio.sleep(delay)

        error_message = f"{operation_name} failed after {self.config.monitor.max_retry_attempts} attempts: {last_error}"
        self.last_runtime_error = error_message
        self.degraded = True
        raise RuntimeError(error_message) from last_error
