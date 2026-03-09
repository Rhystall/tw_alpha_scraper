from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .models import FollowEvent, RuntimeSnapshot, TargetConfig, TargetRecord, WorkerHealthRecord


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class AppDatabase:
    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA foreign_keys=ON;")

    def close(self) -> None:
        self._conn.close()

    def initialize(self) -> None:
        with closing(self._conn.cursor()) as cur:
            cur.executescript(
                """
                CREATE TABLE IF NOT EXISTS targets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL UNIQUE,
                    username TEXT,
                    display_name TEXT,
                    label TEXT,
                    poll_interval_seconds INTEGER,
                    active INTEGER NOT NULL DEFAULT 1,
                    last_seen_followed_user_id TEXT,
                    last_polled_at TEXT,
                    last_success_at TEXT,
                    last_error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS monitor_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS follow_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    target_user_id TEXT NOT NULL,
                    target_username TEXT,
                    target_display_name TEXT,
                    followed_user_id TEXT NOT NULL,
                    followed_username TEXT,
                    followed_display_name TEXT,
                    followed_bio TEXT,
                    followed_profile_image_url TEXT,
                    observed_at TEXT NOT NULL,
                    notified_at TEXT,
                    payload_json TEXT NOT NULL,
                    UNIQUE(target_user_id, followed_user_id)
                );
                CREATE INDEX IF NOT EXISTS idx_follow_events_target_observed
                    ON follow_events(target_user_id, observed_at DESC);

                CREATE TABLE IF NOT EXISTS worker_health (
                    username TEXT PRIMARY KEY,
                    active INTEGER NOT NULL DEFAULT 0,
                    proxy TEXT,
                    is_healthy INTEGER NOT NULL DEFAULT 1,
                    last_checked_at TEXT NOT NULL,
                    last_success_at TEXT,
                    last_failure_at TEXT,
                    consecutive_failures INTEGER NOT NULL DEFAULT 0,
                    cooldown_until TEXT,
                    last_error TEXT,
                    details_json TEXT
                );

                CREATE TABLE IF NOT EXISTS admin_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    actor_id TEXT NOT NULL,
                    actor_name TEXT,
                    action TEXT NOT NULL,
                    details_json TEXT,
                    created_at TEXT NOT NULL
                );
                """
            )
        self._conn.commit()

    def seed_targets(self, targets: Iterable[TargetConfig]) -> None:
        for target in targets:
            self.upsert_target(
                user_id=str(target.user_id),
                label=target.label,
                poll_interval_seconds=target.poll_interval_override,
                active=True,
            )

    def upsert_target(
        self,
        user_id: str,
        username: str | None = None,
        display_name: str | None = None,
        label: str | None = None,
        poll_interval_seconds: int | None = None,
        active: bool = True,
    ) -> None:
        now = utcnow_iso()
        existing = self.get_target(user_id)
        if existing:
            self._conn.execute(
                """
                UPDATE targets
                SET username = COALESCE(?, username),
                    display_name = COALESCE(?, display_name),
                    label = COALESCE(?, label),
                    poll_interval_seconds = COALESCE(?, poll_interval_seconds),
                    active = ?,
                    updated_at = ?
                WHERE user_id = ?
                """,
                (
                    username,
                    display_name,
                    label,
                    poll_interval_seconds,
                    1 if active else 0,
                    now,
                    user_id,
                ),
            )
        else:
            self._conn.execute(
                """
                INSERT INTO targets (
                    user_id, username, display_name, label, poll_interval_seconds,
                    active, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    username,
                    display_name,
                    label,
                    poll_interval_seconds,
                    1 if active else 0,
                    now,
                    now,
                ),
            )
        self._conn.commit()

    def list_targets(self, active_only: bool = False) -> list[TargetRecord]:
        query = "SELECT * FROM targets"
        params: tuple[Any, ...] = ()
        if active_only:
            query += " WHERE active = 1"
        query += " ORDER BY COALESCE(label, display_name, username, user_id)"
        rows = self._conn.execute(query, params).fetchall()
        return [self._row_to_target(row) for row in rows]

    def get_target(self, identifier: str) -> TargetRecord | None:
        row = self._conn.execute(
            """
            SELECT * FROM targets
            WHERE user_id = ? OR username = ? OR label = ?
            LIMIT 1
            """,
            (identifier, identifier.lstrip("@"), identifier),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_target(row)

    def deactivate_target(self, identifier: str) -> bool:
        target = self.get_target(identifier)
        if not target:
            return False
        now = utcnow_iso()
        self._conn.execute(
            "UPDATE targets SET active = 0, updated_at = ? WHERE user_id = ?",
            (now, target.user_id),
        )
        self._conn.commit()
        return True

    def record_follow_event(self, event: FollowEvent) -> int | None:
        cur = self._conn.execute(
            """
            INSERT OR IGNORE INTO follow_events (
                target_user_id, target_username, target_display_name,
                followed_user_id, followed_username, followed_display_name,
                followed_bio, followed_profile_image_url, observed_at, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.target_user_id,
                event.target_username,
                event.target_display_name,
                event.followed_user_id,
                event.followed_username,
                event.followed_display_name,
                event.followed_bio,
                event.followed_profile_image_url,
                event.observed_at,
                event.payload_json,
            ),
        )
        self._conn.commit()
        if cur.rowcount == 0:
            return None
        return cur.lastrowid or None

    def mark_event_notified(self, event_id: int) -> None:
        now = utcnow_iso()
        self._conn.execute(
            "UPDATE follow_events SET notified_at = ? WHERE id = ?",
            (now, event_id),
        )
        self._conn.commit()
        self.set_state("last_alert_at", now)

    def recent_follow_events(self, limit: int = 5) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT target_user_id, target_username, target_display_name,
                   followed_user_id, followed_username, followed_display_name,
                   observed_at, notified_at
            FROM follow_events
            ORDER BY observed_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]

    def set_target_poll_success(
        self,
        user_id: str,
        last_seen_followed_user_id: str | None,
        username: str | None = None,
        display_name: str | None = None,
    ) -> None:
        now = utcnow_iso()
        self._conn.execute(
            """
            UPDATE targets
            SET last_seen_followed_user_id = COALESCE(?, last_seen_followed_user_id),
                last_polled_at = ?,
                last_success_at = ?,
                last_error = NULL,
                username = COALESCE(?, username),
                display_name = COALESCE(?, display_name),
                updated_at = ?
            WHERE user_id = ?
            """,
            (last_seen_followed_user_id, now, now, username, display_name, now, user_id),
        )
        self._conn.commit()

    def set_target_poll_failure(self, user_id: str, error: str) -> None:
        now = utcnow_iso()
        self._conn.execute(
            """
            UPDATE targets
            SET last_polled_at = ?, last_error = ?, updated_at = ?
            WHERE user_id = ?
            """,
            (now, error, now, user_id),
        )
        self._conn.commit()
        self.set_state("last_runtime_error", error)

    def set_target_last_seen(self, user_id: str, last_seen_followed_user_id: str | None) -> None:
        now = utcnow_iso()
        self._conn.execute(
            """
            UPDATE targets
            SET last_seen_followed_user_id = ?, updated_at = ?
            WHERE user_id = ?
            """,
            (last_seen_followed_user_id, now, user_id),
        )
        self._conn.commit()

    def set_state(self, key: str, value: Any) -> None:
        now = utcnow_iso()
        payload = json.dumps(value)
        self._conn.execute(
            """
            INSERT INTO monitor_state (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            (key, payload, now),
        )
        self._conn.commit()

    def get_state(self, key: str, default: Any = None) -> Any:
        row = self._conn.execute(
            "SELECT value FROM monitor_state WHERE key = ?",
            (key,),
        ).fetchone()
        if row is None:
            return default
        return json.loads(row["value"])

    def set_paused(self, paused: bool) -> None:
        self.set_state("paused", paused)

    def is_paused(self) -> bool:
        return bool(self.get_state("paused", False))

    def record_admin_action(
        self,
        actor_id: str,
        actor_name: str | None,
        action: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO admin_actions (actor_id, actor_name, action, details_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                actor_id,
                actor_name,
                action,
                json.dumps(details or {}),
                utcnow_iso(),
            ),
        )
        self._conn.commit()

    def upsert_worker_health(self, account: dict[str, Any]) -> None:
        now = utcnow_iso()
        username = str(account.get("username", "unknown"))
        active = bool(account.get("active", False))
        last_error = account.get("error") or account.get("last_error")
        previous = self._conn.execute(
            "SELECT consecutive_failures FROM worker_health WHERE username = ?",
            (username,),
        ).fetchone()
        previous_failures = int(previous["consecutive_failures"]) if previous else 0
        consecutive_failures = 0 if active and not last_error else previous_failures + 1
        self._conn.execute(
            """
            INSERT INTO worker_health (
                username, active, proxy, is_healthy, last_checked_at, last_success_at,
                last_failure_at, consecutive_failures, cooldown_until, last_error, details_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET
                active = excluded.active,
                proxy = excluded.proxy,
                is_healthy = excluded.is_healthy,
                last_checked_at = excluded.last_checked_at,
                last_success_at = excluded.last_success_at,
                last_failure_at = excluded.last_failure_at,
                consecutive_failures = excluded.consecutive_failures,
                cooldown_until = excluded.cooldown_until,
                last_error = excluded.last_error,
                details_json = excluded.details_json
            """,
            (
                username,
                1 if active else 0,
                account.get("proxy"),
                1 if active and not last_error else 0,
                now,
                now if active and not last_error else None,
                now if last_error else None,
                consecutive_failures,
                account.get("cooldown_until"),
                last_error,
                json.dumps(account, default=str),
            ),
        )
        self._conn.commit()

    def list_worker_health(self) -> list[WorkerHealthRecord]:
        rows = self._conn.execute(
            "SELECT * FROM worker_health ORDER BY username"
        ).fetchall()
        return [
            WorkerHealthRecord(
                username=row["username"],
                active=bool(row["active"]),
                proxy=row["proxy"],
                is_healthy=bool(row["is_healthy"]),
                last_checked_at=row["last_checked_at"],
                last_success_at=row["last_success_at"],
                last_failure_at=row["last_failure_at"],
                consecutive_failures=row["consecutive_failures"],
                cooldown_until=row["cooldown_until"],
                last_error=row["last_error"],
                details_json=row["details_json"],
            )
            for row in rows
        ]

    def build_runtime_snapshot(
        self,
        started_at: str,
        paused: bool,
        degraded: bool,
        last_cycle_at: str | None,
        last_alert_at: str | None,
        last_runtime_error: str | None,
    ) -> RuntimeSnapshot:
        active_targets = self._conn.execute(
            "SELECT COUNT(*) AS count FROM targets WHERE active = 1"
        ).fetchone()["count"]
        worker_stats = self._conn.execute(
            """
            SELECT COUNT(*) AS total,
                   COALESCE(SUM(CASE WHEN is_healthy = 1 THEN 1 ELSE 0 END), 0) AS healthy
            FROM worker_health
            """
        ).fetchone()
        return RuntimeSnapshot(
            started_at=started_at,
            paused=paused,
            degraded=degraded,
            last_cycle_at=last_cycle_at,
            last_alert_at=last_alert_at,
            last_runtime_error=last_runtime_error,
            active_targets=int(active_targets),
            healthy_workers=int(worker_stats["healthy"]),
            total_workers=int(worker_stats["total"]),
            recent_events=self.recent_follow_events(),
        )

    def export_status(self) -> dict[str, Any]:
        return {
            "targets": [asdict(target) for target in self.list_targets()],
            "paused": self.is_paused(),
            "recent_events": self.recent_follow_events(),
            "workers": [asdict(worker) for worker in self.list_worker_health()],
        }

    @staticmethod
    def _row_to_target(row: sqlite3.Row) -> TargetRecord:
        return TargetRecord(
            user_id=row["user_id"],
            username=row["username"],
            display_name=row["display_name"],
            label=row["label"],
            poll_interval_seconds=row["poll_interval_seconds"],
            active=bool(row["active"]),
            last_seen_followed_user_id=row["last_seen_followed_user_id"],
            last_polled_at=row["last_polled_at"],
            last_success_at=row["last_success_at"],
            last_error=row["last_error"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
