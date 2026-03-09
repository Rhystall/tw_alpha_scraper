from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .models import AppConfig, DiscordSettings, MonitorSettings, StorageSettings, TargetConfig


def _load_dotenv(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("\"'")
    return values


def _env_or_data(key: str, data: dict[str, Any], env: dict[str, str], default: Any = None) -> Any:
    if key in env:
        return env[key]
    return data.get(key, default)


def _get_nested(data: dict[str, Any], *keys: str, default: Any = None) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
        if current is None:
            return default
    return current


def _parse_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _parse_int(value: Any, default: int | None = None) -> int | None:
    if value in (None, ""):
        return default
    return int(value)


def _parse_float(value: Any, default: float | None = None) -> float | None:
    if value in (None, ""):
        return default
    return float(value)


def _parse_int_list(value: Any) -> tuple[int, ...]:
    if value in (None, "", []):
        return ()
    if isinstance(value, (list, tuple)):
        return tuple(int(item) for item in value)
    return tuple(int(item.strip()) for item in str(value).split(",") if item.strip())


def _parse_targets(raw_targets: list[Any] | None) -> list[TargetConfig]:
    targets: list[TargetConfig] = []
    for raw in raw_targets or []:
        if isinstance(raw, str):
            targets.append(TargetConfig(user_id=raw))
            continue
        if isinstance(raw, dict) and raw.get("user_id"):
            targets.append(
                TargetConfig(
                    user_id=str(raw["user_id"]),
                    label=raw.get("label"),
                    poll_interval_override=_parse_int(raw.get("poll_interval_override")),
                )
            )
    return targets


def load_config(config_path: str | None = None, env_path: str | None = None) -> AppConfig:
    config_path_value = config_path or os.getenv("TW_ALPHA_CONFIG_PATH", "config.json")
    env_path_value = env_path or os.getenv("TW_ALPHA_ENV_PATH", ".env")

    env_file_values = _load_dotenv(Path(env_path_value))
    merged_env = {**env_file_values, **os.environ}

    config_payload: dict[str, Any] = {}
    config_file = Path(config_path_value)
    if config_file.exists():
        config_payload = json.loads(config_file.read_text())

    discord_data = _get_nested(config_payload, "discord", default={}) or {}
    monitor_data = _get_nested(config_payload, "monitor", default={}) or {}
    storage_data = _get_nested(config_payload, "storage", default={}) or {}

    discord = DiscordSettings(
        alert_webhook_url=_env_or_data(
            "DISCORD_ALERT_WEBHOOK_URL",
            discord_data,
            merged_env,
            discord_data.get("alert_webhook_url"),
        ),
        bot_token=_env_or_data(
            "DISCORD_BOT_TOKEN",
            discord_data,
            merged_env,
            discord_data.get("bot_token"),
        ),
        guild_id=_parse_int(
            _env_or_data("DISCORD_GUILD_ID", discord_data, merged_env, discord_data.get("guild_id"))
        ),
        admin_channel_id=_parse_int(
            _env_or_data(
                "DISCORD_ADMIN_CHANNEL_ID",
                discord_data,
                merged_env,
                discord_data.get("admin_channel_id"),
            )
        ),
        admin_role_ids=_parse_int_list(
            _env_or_data(
                "DISCORD_ADMIN_ROLE_IDS",
                discord_data,
                merged_env,
                discord_data.get("admin_role_ids"),
            )
        ),
    )

    monitor = MonitorSettings(
        default_poll_interval_seconds=_parse_int(
            _env_or_data(
                "MONITOR_DEFAULT_POLL_INTERVAL_SECONDS",
                monitor_data,
                merged_env,
                monitor_data.get("default_poll_interval_seconds", 300),
            ),
            300,
        )
        or 300,
        pause_on_start=_parse_bool(
            _env_or_data(
                "MONITOR_PAUSE_ON_START",
                monitor_data,
                merged_env,
                monitor_data.get("pause_on_start", False),
            )
        ),
        target_jitter_min_seconds=_parse_float(
            _env_or_data(
                "MONITOR_TARGET_JITTER_MIN_SECONDS",
                monitor_data,
                merged_env,
                monitor_data.get("target_jitter_min_seconds", 3.0),
            ),
            3.0,
        )
        or 3.0,
        target_jitter_max_seconds=_parse_float(
            _env_or_data(
                "MONITOR_TARGET_JITTER_MAX_SECONDS",
                monitor_data,
                merged_env,
                monitor_data.get("target_jitter_max_seconds", 9.0),
            ),
            9.0,
        )
        or 9.0,
        scheduler_tick_seconds=_parse_int(
            _env_or_data(
                "MONITOR_SCHEDULER_TICK_SECONDS",
                monitor_data,
                merged_env,
                monitor_data.get("scheduler_tick_seconds", 15),
            ),
            15,
        )
        or 15,
        max_retry_attempts=_parse_int(
            _env_or_data(
                "MONITOR_MAX_RETRY_ATTEMPTS",
                monitor_data,
                merged_env,
                monitor_data.get("max_retry_attempts", 3),
            ),
            3,
        )
        or 3,
        retry_base_delay_seconds=_parse_float(
            _env_or_data(
                "MONITOR_RETRY_BASE_DELAY_SECONDS",
                monitor_data,
                merged_env,
                monitor_data.get("retry_base_delay_seconds", 2.0),
            ),
            2.0,
        )
        or 2.0,
        max_follow_scan=_parse_int(
            _env_or_data(
                "MONITOR_MAX_FOLLOW_SCAN",
                monitor_data,
                merged_env,
                monitor_data.get("max_follow_scan", 100),
            ),
            100,
        )
        or 100,
        api_timeout_seconds=_parse_int(
            _env_or_data(
                "MONITOR_API_TIMEOUT_SECONDS",
                monitor_data,
                merged_env,
                monitor_data.get("api_timeout_seconds", 60),
            ),
            60,
        )
        or 60,
        worker_cooldown_seconds=_parse_int(
            _env_or_data(
                "MONITOR_WORKER_COOLDOWN_SECONDS",
                monitor_data,
                merged_env,
                monitor_data.get("worker_cooldown_seconds", 900),
            ),
            900,
        )
        or 900,
    )

    storage = StorageSettings(
        app_db_path=str(
            _env_or_data(
                "STORAGE_APP_DB_PATH",
                storage_data,
                merged_env,
                storage_data.get("app_db_path", "data/tw_alpha_scraper.db"),
            )
        ),
        legacy_state_path=str(
            _env_or_data(
                "STORAGE_LEGACY_STATE_PATH",
                storage_data,
                merged_env,
                storage_data.get("legacy_state_path", "state.json"),
            )
        ),
        log_file_path=str(
            _env_or_data(
                "LOG_FILE_PATH",
                storage_data,
                merged_env,
                storage_data.get("log_file_path", "logs/tw_alpha_scraper.log"),
            )
        ),
    )

    targets = _parse_targets(config_payload.get("targets"))

    return AppConfig(discord=discord, monitor=monitor, storage=storage, targets=targets)
