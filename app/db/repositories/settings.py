from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Setting


class SettingsRepository:
    async def get(self, session: AsyncSession, key: str) -> str | None:
        res = await session.execute(select(Setting.value).where(Setting.key == key))
        return res.scalar_one_or_none()

    async def set(self, session: AsyncSession, key: str, value: str) -> None:
        res = await session.execute(select(Setting).where(Setting.key == key))
        row = res.scalar_one_or_none()
        if not row:
            session.add(Setting(key=key, value=value))
        else:
            row.value = value
            session.add(row)
        await session.flush()
