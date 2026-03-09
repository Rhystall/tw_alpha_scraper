from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class DiscordSettings:
    alert_webhook_url: str | None = None
    bot_token: str | None = None
    guild_id: int | None = None
    admin_channel_id: int | None = None
    admin_role_ids: tuple[int, ...] = ()


@dataclass(slots=True)
class MonitorSettings:
    default_poll_interval_seconds: int = 300
    pause_on_start: bool = False
    target_jitter_min_seconds: float = 3.0
    target_jitter_max_seconds: float = 9.0
    scheduler_tick_seconds: int = 15
    max_retry_attempts: int = 3
    retry_base_delay_seconds: float = 2.0
    max_follow_scan: int = 100
    api_timeout_seconds: int = 60
    worker_cooldown_seconds: int = 900


@dataclass(slots=True)
class StorageSettings:
    app_db_path: str = "data/tw_alpha_scraper.db"
    legacy_state_path: str = "state.json"
    log_file_path: str = "logs/tw_alpha_scraper.log"


@dataclass(slots=True)
class TargetConfig:
    user_id: str
    label: str | None = None
    poll_interval_override: int | None = None


@dataclass(slots=True)
class AppConfig:
    discord: DiscordSettings = field(default_factory=DiscordSettings)
    monitor: MonitorSettings = field(default_factory=MonitorSettings)
    storage: StorageSettings = field(default_factory=StorageSettings)
    targets: list[TargetConfig] = field(default_factory=list)


@dataclass(slots=True)
class ResolvedUser:
    id: str
    username: str | None = None
    display_name: str | None = None
    description: str | None = None
    profile_image_url: str | None = None
    raw: Any | None = None


@dataclass(slots=True)
class TargetRecord:
    user_id: str
    username: str | None
    display_name: str | None
    label: str | None
    poll_interval_seconds: int | None
    active: bool
    last_seen_followed_user_id: str | None
    last_polled_at: str | None
    last_success_at: str | None
    last_error: str | None
    created_at: str
    updated_at: str

    def poll_interval(self, default_seconds: int) -> int:
        return self.poll_interval_seconds or default_seconds

    def display_label(self) -> str:
        return self.label or self.display_name or self.username or self.user_id


@dataclass(slots=True)
class FollowEvent:
    target_user_id: str
    target_username: str | None
    target_display_name: str | None
    followed_user_id: str
    followed_username: str | None
    followed_display_name: str | None
    followed_bio: str | None
    followed_profile_image_url: str | None
    observed_at: str
    payload_json: str


@dataclass(slots=True)
class WorkerHealthRecord:
    username: str
    active: bool
    proxy: str | None
    is_healthy: bool
    last_checked_at: str
    last_success_at: str | None
    last_failure_at: str | None
    consecutive_failures: int
    cooldown_until: str | None
    last_error: str | None
    details_json: str | None


@dataclass(slots=True)
class RuntimeSnapshot:
    started_at: str
    paused: bool
    degraded: bool
    last_cycle_at: str | None
    last_alert_at: str | None
    last_runtime_error: str | None
    active_targets: int
    healthy_workers: int
    total_workers: int
    recent_events: list[dict[str, Any]]


@dataclass(slots=True)
class AdminActor:
    actor_id: str
    actor_name: str | None = None


@dataclass(slots=True)
class CommandResult:
    ok: bool
    message: str
    payload: dict[str, Any] | None = None


@dataclass(slots=True)
class SyncResult:
    target_user_id: str
    target_label: str
    bootstrapped: bool
    fetched_count: int
    inserted_count: int
    notified_count: int
    last_seen_followed_user_id: str | None
    observed_at: datetime
