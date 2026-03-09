import json

from tw_alpha_scraper.config import load_config


def test_load_config_supports_env_overrides(tmp_path):
    config_path = tmp_path / "config.json"
    env_path = tmp_path / ".env"

    config_path.write_text(
        json.dumps(
            {
                "discord": {
                    "bot_token": "json-token",
                    "guild_id": 111,
                    "admin_role_ids": [222],
                },
                "monitor": {"default_poll_interval_seconds": 300},
                "storage": {"app_db_path": "data/from-json.db"},
                "targets": [{"user_id": "123", "label": "alpha"}],
            }
        )
    )
    env_path.write_text(
        "\n".join(
            [
                "DISCORD_BOT_TOKEN=env-token",
                "MONITOR_DEFAULT_POLL_INTERVAL_SECONDS=120",
                "DISCORD_ADMIN_ROLE_IDS=333,444",
                "STORAGE_APP_DB_PATH=data/from-env.db",
            ]
        )
    )

    config = load_config(str(config_path), str(env_path))

    assert config.discord.bot_token == "env-token"
    assert config.discord.admin_role_ids == (333, 444)
    assert config.monitor.default_poll_interval_seconds == 120
    assert config.storage.app_db_path == "data/from-env.db"
    assert config.targets[0].user_id == "123"
    assert config.targets[0].label == "alpha"
