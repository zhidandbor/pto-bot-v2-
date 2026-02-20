from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.audit_log import AuditLogRepository


@dataclass(frozen=True)
class AuditService:
    repo: AuditLogRepository

    async def log(
        self,
        session: AsyncSession,
        *,
        actor_user_id: int,
        action: str,
        entity_type: str,
        entity_id: str | None,
        payload: dict[str, Any],
    ) -> None:
        await self.repo.add(
            session,
            actor_user_id=actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            payload=payload,
        )
