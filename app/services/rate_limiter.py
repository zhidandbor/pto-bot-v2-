from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.repositories.rate_limits import RateLimitsRepository
from app.services.settings_service import SettingsService


@dataclass(frozen=True)
class RateLimiter:
    settings: Settings
    settings_service: SettingsService
    repo: RateLimitsRepository

    async def check_and_touch(
        self,
        session: AsyncSession,
        *,
        scope_type: str,
        scope_id: int,
        now: datetime | None = None,
    ) -> tuple[bool, int]:
        now = now or datetime.now(timezone.utc)
        cooldown_minutes = await self.settings_service.get_cooldown_minutes(session)
        if cooldown_minutes <= 0:
            await self.repo.upsert(session, scope_type=scope_type, scope_id=scope_id, last_request_at=now)
            return True, 0

        row = await self.repo.get(session, scope_type=scope_type, scope_id=scope_id)
        if not row:
            await self.repo.upsert(session, scope_type=scope_type, scope_id=scope_id, last_request_at=now)
            return True, 0

        next_allowed = row.last_request_at.replace(tzinfo=timezone.utc) + timedelta(minutes=cooldown_minutes)
        if now < next_allowed:
            remaining = int((next_allowed - now).total_seconds()
