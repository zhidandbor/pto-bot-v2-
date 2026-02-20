from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select, delete, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Object, ObjectGroupLink


class ObjectsRepository:
    async def get_by_id(self, session: AsyncSession, object_id: int) -> Object | None:
        res = await session.execute(select(Object).where(Object.id == object_id))
        return res.scalar_one_or_none()

    async def list(self, session: AsyncSession, limit: int = 200) -> list[Object]:
        res = await session.execute(select(Object).order_by(Object.id.desc()).limit(limit))
        return list(res.scalars().all())

    async def delete(self, session: AsyncSession, object_id: int) -> bool:
        res = await session.execute(delete(Object).where(Object.id == object_id).returning(Object.id))
        deleted = res.scalar_one_or_none()
        return deleted is not None

    async def upsert_by_dedup_key(
        self,
        session: AsyncSession,
        *,
        dedup_key: str,
        fields: dict[str, Any],
    ) -> tuple[Object, bool]:
        res = await session.execute(select(Object).where(Object.dedup_key == dedup_key))
        obj = res.scalar_one_or_none()
        created = False
        if not obj:
            obj = Object(dedup_key=dedup_key, **fields)
            session.add(obj)
            await session.flush()
            created = True
        else:
            for k, v in fields.items():
                setattr(obj, k, v)
            session.add(obj)
            await session.flush()
        return obj, created

    async def search(self, session: AsyncSession, query: str, limit: int = 25) -> list[Object]:
        q = (query or "").strip()
        if not q:
            return []
        like = f"%{q.lower()}%"
        stmt = (
            select(Object)
            .where(
                or_(
                    Object.ps_number.ilike(like),
                    Object.ps_name.ilike(like),
                    Object.title_name.ilike(like),
                    Object.address.ilike(like),
                    Object.contract_number.ilike(like),
                    Object.request_number.ilike(like),
                    Object.work_type.ilike(like),
                )
            )
            .order_by(Object.id.desc())
            .limit(limit)
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())

    async def link_group(self, session: AsyncSession, *, object_id: int, chat_id: int) -> None:
        stmt = select(ObjectGroupLink).where(and_(ObjectGroupLink.object_id == object_id, ObjectGroupLink.chat_id == chat_id))
        res = await session.execute(stmt)
        if res.scalar_one_or_none() is None:
            session.add(ObjectGroupLink(object_id=object_id, chat_id=chat_id))
            await session.flush()

    async def unlink_group(self, session: AsyncSession, *, object_id: int, chat_id: int) -> bool:
        res = await session.execute(
            delete(ObjectGroupLink)
            .where(and_(ObjectGroupLink.object_id == object_id, ObjectGroupLink.chat_id == chat_id))
            .returning(ObjectGroupLink.id)
        )
        return res.scalar_one_or_none() is not None

    async def list_linked_objects(self, session: AsyncSession, chat_id: int) -> list[Object]:
        stmt = (
            select(Object)
            .join(ObjectGroupLink, ObjectGroupLink.object_id == Object.id)
            .where(ObjectGroupLink.chat_id == chat_id)
            .order_by(Object.id.desc())
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())

    async def list_group_links(self, session: AsyncSession, chat_id: int | None = None) -> list[tuple[int, int]]:
        stmt = select(ObjectGroupLink.object_id, ObjectGroupLink.chat_id).order_by(ObjectGroupLink.chat_id, ObjectGroupLink.object_id)
        if chat_id is not None:
            stmt = stmt.where(ObjectGroupLink.chat_id == chat_id)
        res = await session.execute(stmt)
        return [(int(a), int(b)) for a, b in res.all()]
