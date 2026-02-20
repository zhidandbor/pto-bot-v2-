from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLog


class AuditLogRepository:
    async def add(
        self,
        session: AsyncSession,
        *,
        actor_user_id: int,
        action: str,
        entity_type: str,
        entity_id: str | None,
        payload: dict[str, Any],
    ) -> None:
        session.add(
            AuditLog(
                actor_user_id=actor_user_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                payload=payload,
            )
        )
        await session.flush()
