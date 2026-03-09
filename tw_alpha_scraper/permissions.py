from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(slots=True)
class AccessPolicy:
    admin_channel_id: int | None = None
    admin_role_ids: tuple[int, ...] = ()

    def is_allowed(
        self,
        channel_id: int | None,
        role_ids: Iterable[int],
        manage_guild: bool = False,
    ) -> bool:
        role_id_set = set(role_ids)
        if self.admin_channel_id and channel_id == self.admin_channel_id:
            return True
        if self.admin_role_ids and role_id_set.intersection(self.admin_role_ids):
            return True
        if not self.admin_channel_id and not self.admin_role_ids and manage_guild:
            return True
        return False
