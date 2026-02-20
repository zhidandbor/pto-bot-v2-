from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User


class UsersRepository:
    async def get_or_create(
        self,
        session: AsyncSession,
        *,
        telegram_user_id: int,
        username: str | None,
        full_name: str | None,
    ) -> User:
        res = await session.execute(select(User).where(User.telegram_user_id == telegram_user_id))
        user = res.scalar_one_or_none()
        if user:
            changed = False
            if username is not None and user.username != username:
                user.username = username
                changed = True
            if full_name is not None and user.full_name != full_name:
                user.full_name = full_name
                changed = True
            if changed:
                session.add(user)
            return user

        user = User(
            telegram_user_id=telegram_user_id,
            username=username,
            full_name=full_name,
            is_allowed_private=False,
        )
        session.add(user)
        await session.flush()
        return user

    async def is_allowed_private(self, session: AsyncSession, telegram_user_id: int) -> bool:
        res = await session.execute(select(User.is_allowed_private).where(User.telegram_user_id == telegram_user_id))
        val = res.scalar_one_or_none()
        return bool(val)

    async def set_allowed_private(self, session: AsyncSession, telegram_user_id: int, allowed: bool) -> None:
        res = await session.execute(select(User).where(User.telegram_user_id == telegram_user_id))
        user = res.scalar_one_or_none()
        if not user:
            user = User(telegram_user_id=telegram_user_id, is_allowed_private=allowed, username=None, full_name=None)
            session.add(user)
        else:
            user.is_allowed_private = allowed
            session.add(user)
        await session.flush()

    async def list_allowed_private(self, session: AsyncSession) -> list[User]:
        res = await session.execute(select(User).where(User.is_allowed_private.is_(True)).order_by(User.telegram_user_id))
        return list(res.scalars().all())
