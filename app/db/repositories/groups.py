from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Group


class GroupsRepository:
    async def ensure_group(self, session: AsyncSession, *, chat_id: int, title: str | None, added_by: int | None) -> Group:
        res = await session.execute(select(Group).where(Group.chat_id == chat_id))
        g = res.scalar_one_or_none()
        if g:
            if title is not None:
                g.title = title
            if added_by is not None:
                g.added_by = added_by
            session.add(g)
            await session.flush()
            return g
        g = Group(chat_id=chat_id, title=title, added_by=added_by)
        session.add(g)
        await session.flush()
        return g

    async def get(self, session: AsyncSession, chat_id: int) -> Group | None:
        res = await session.execute(select(Group).where(Group.chat_id == chat_id))
        return res.scalar_one_or_none()
