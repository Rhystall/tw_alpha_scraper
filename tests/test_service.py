import logging

import pytest

from tw_alpha_scraper.models import AppConfig, DiscordSettings, MonitorSettings, ResolvedUser, StorageSettings
from tw_alpha_scraper.service import AlphaMonitorService
from tw_alpha_scraper.storage import AppDatabase


class FakeTwitterClient:
    def __init__(self):
        self.follow_map: dict[str, list[ResolvedUser]] = {}
        self.resolve_map: dict[str, ResolvedUser] = {}
        self.accounts = [{"username": "worker-1", "active": True, "proxy": None}]
        self.fail_fetch_attempts = 0

    async def resolve_user(self, identifier: str) -> ResolvedUser:
        return self.resolve_map[identifier]

    async def iter_following(self, user_id: str, limit: int | None = None):
        if self.fail_fetch_attempts:
            self.fail_fetch_attempts -= 1
            raise RuntimeError("temporary failure")

        users = self.follow_map.get(user_id, [])
        if limit is not None:
            users = users[:limit]
        for user in users:
            yield user

    async def list_accounts(self):
        return self.accounts


class FakeNotifier:
    def __init__(self):
        self.sent: list[tuple[str, str]] = []

    async def send_follow_alert(self, target, followed_user):
        self.sent.append((target.user_id, followed_user.id))
        return True


@pytest.mark.asyncio
async def test_sync_target_bootstraps_without_spamming_backlog(tmp_path):
    db = AppDatabase(str(tmp_path / "app.db"))
    config = AppConfig(
        discord=DiscordSettings(),
        monitor=MonitorSettings(default_poll_interval_seconds=60, retry_base_delay_seconds=0),
        storage=StorageSettings(app_db_path=str(tmp_path / "app.db")),
    )
    twitter = FakeTwitterClient()
    notifier = FakeNotifier()
    service = AlphaMonitorService(config, db, twitter_client=twitter, notifier=notifier, logger=logging.getLogger("test"))

    await service.initialize()
    db.upsert_target("100", username="alpha", display_name="Alpha")
    twitter.follow_map["100"] = [
        ResolvedUser(id="200", username="beta", display_name="Beta"),
        ResolvedUser(id="201", username="gamma", display_name="Gamma"),
    ]

    first_sync = await service.sync_target("100", send_alerts=True)

    assert first_sync.bootstrapped is True
    assert notifier.sent == []

    twitter.follow_map["100"] = [
        ResolvedUser(id="300", username="delta", display_name="Delta"),
        ResolvedUser(id="200", username="beta", display_name="Beta"),
    ]
    second_sync = await service.sync_target("100", send_alerts=True)

    assert second_sync.bootstrapped is False
    assert second_sync.inserted_count == 1
    assert second_sync.notified_count == 1
    assert notifier.sent == [("100", "300")]


@pytest.mark.asyncio
async def test_add_target_bootstraps_and_remove_target_deactivates(tmp_path):
    db = AppDatabase(str(tmp_path / "app.db"))
    config = AppConfig(
        monitor=MonitorSettings(retry_base_delay_seconds=0),
        storage=StorageSettings(app_db_path=str(tmp_path / "app.db")),
    )
    twitter = FakeTwitterClient()
    notifier = FakeNotifier()
    twitter.resolve_map["@alpha"] = ResolvedUser(id="100", username="alpha", display_name="Alpha")
    twitter.follow_map["100"] = [ResolvedUser(id="200", username="beta", display_name="Beta")]
    service = AlphaMonitorService(config, db, twitter_client=twitter, notifier=notifier, logger=logging.getLogger("test"))

    await service.initialize()
    add_result = await service.add_target("@alpha", label="alpha-list")
    remove_result = await service.remove_target("100")

    assert add_result.ok is True
    assert "Bootstrap completed" in add_result.message
    assert db.get_target("100") is not None
    assert remove_result.ok is True
    assert db.get_target("100").active is False


@pytest.mark.asyncio
async def test_sync_target_recovers_after_retry(tmp_path):
    db = AppDatabase(str(tmp_path / "app.db"))
    config = AppConfig(
        monitor=MonitorSettings(max_retry_attempts=2, retry_base_delay_seconds=0),
        storage=StorageSettings(app_db_path=str(tmp_path / "app.db")),
    )
    twitter = FakeTwitterClient()
    notifier = FakeNotifier()
    service = AlphaMonitorService(config, db, twitter_client=twitter, notifier=notifier, logger=logging.getLogger("test"))

    await service.initialize()
    db.upsert_target("100", username="alpha", display_name="Alpha")
    db.set_target_last_seen("100", "200")
    twitter.follow_map["100"] = [ResolvedUser(id="300", username="delta", display_name="Delta")]
    twitter.fail_fetch_attempts = 1

    result = await service.sync_target("100", send_alerts=True)

    assert result.inserted_count == 1
    assert result.notified_count == 1
    assert service.degraded is False
