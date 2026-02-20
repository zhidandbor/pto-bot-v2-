from __future__ import annotations

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Admin


class AdminRepository:
    async def is_admin(self, session: AsyncSession, telegram_user_id: int) -> bool:
        res = await session.execute(select(Admin.telegram_user_id).where(Admin.telegram_user_id == telegram_user_id))
        return res.scalar_one_or_none() is not None

    async def add(self, session: AsyncSession, telegram_user_id: int) -> None:
        exists = await self.is_admin(session, telegram_user_id)
        if not exists:
            session.add(Admin(telegram_user_id=telegram_user_id))
            await session.flush()

    async def remove(self, session: AsyncSession, telegram_user_id: int) -> bool:
        res = await session.execute(delete(Admin).where(Admin.telegram_user_id == telegram_user_id).returning(Admin.telegram_user_id))
        deleted = res.scalar_one_or_none()
        return deleted is not None

    async def list(self, session: AsyncSession) -> list[int]:
        res = await session.execute(select(Admin.telegram_user_id).order_by(Admin.telegram_user_id))
        return list(res.scalars().all())
