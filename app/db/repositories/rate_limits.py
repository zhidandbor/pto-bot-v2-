from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RateLimit


class RateLimitsRepository:
    async def get(self, session: AsyncSession, *, scope_type: str, scope_id: int) -> RateLimit | None:
        res = await session.execute(select(RateLimit).where(RateLimit.scope_type == scope_type, RateLimit.scope_id == scope_id))
        return res.scalar_one_or_none()

    async def upsert(self, session: AsyncSession, *, scope_type: str, scope_id: int, last_request_at: datetime) -> None:
        row = await self.get(session, scope_type=scope_type, scope_id=scope_id)
        if not row:
            session.add(RateLimit(scope_type=scope_type, scope_id=scope_id, last_request_at=last_request_at))
        else:
            row.last_request_at = last_request_at
            session.add(row)
        await session.flush()
