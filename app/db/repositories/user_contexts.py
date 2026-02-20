from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import UserContext


class UserContextsRepository:
    async def get_or_create(self, session: AsyncSession, *, telegram_user_id: int, chat_id: int) -> UserContext:
        res = await session.execute(
            select(UserContext).where(UserContext.telegram_user_id == telegram_user_id, UserContext.chat_id == chat_id)
        )
        row = res.scalar_one_or_none()
        if row:
            return row
        row = UserContext(telegram_user_id=telegram_user_id, chat_id=chat_id, pending_payload={})
        session.add(row)
        await session.flush()
        return row

    async def set_selected_object(
        self,
        session: AsyncSession,
        *,
        telegram_user_id: int,
        chat_id: int,
        object_id: int,
        selected_at: datetime,
        expires_at: datetime | None,
    ) -> None:
        row = await self.get_or_create(session, telegram_user_id=telegram_user_id, chat_id=chat_id)
        row.selected_object_id = object_id
        row.selected_at = selected_at
        row.expires_at = expires_at
        session.add(row)
        await session.flush()

    async def get_selected_object_id(self, session: AsyncSession, *, telegram_user_id: int, chat_id: int, now: datetime) -> int | None:
        res = await session.execute(
            select(UserContext).where(UserContext.telegram_user_id == telegram_user_id, UserContext.chat_id == chat_id)
        )
        row = res.scalar_one_or_none()
        if not row or not row.selected_object_id:
            return None
        if row.expires_at and row.expires_at <= now:
            return None
        return int(row.selected_object_id)

    async def set_pending_action(
        self,
        session: AsyncSession,
        *,
        telegram_user_id: int,
        chat_id: int,
        command: str,
        payload: dict[str, Any],
        expires_at: datetime,
    ) -> None:
        row = await self.get_or_create(session, telegram_user_id=telegram_user_id, chat_id=chat_id)
        row.pending_command = command
        row.pending_payload = payload
        row.pending_expires_at = expires_at
        session.add(row)
        await session.flush()

    async def pop_pending_action(self, session: AsyncSession, *, telegram_user_id: int, chat_id: int, now: datetime) -> tuple[str | None, dict[str, Any]]:
        row = await self.get_or_create(session, telegram_user_id=telegram_user_id, chat_id=chat_id)
        if not row.pending_command or not row.pending_expires_at or row.pending_expires_at <= now:
            row.pending_command = None
            row.pending_payload = {}
            row.pending_expires_at = None
            session.add(row)
            await session.flush()
            return None, {}
        cmd = row.pending_command
        payload = dict(row.pending_payload or {})
        row.pending_command = None
        row.pending_payload = {}
        row.pending_expires_at = None
        session.add(row)
        await session.flush()
        return cmd, payload
