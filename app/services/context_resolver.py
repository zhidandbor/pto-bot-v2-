from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.logging import get_logger
from app.db.repositories.groups import GroupsRepository
from app.db.repositories.objects import ObjectsRepository
from app.db.repositories.user_contexts import UserContextsRepository
from app.services.rbac import RBACService

logger = get_logger(__name__)


def _display_name(obj: object) -> str:
    """Return a human-readable label for an Object row."""
    return getattr(obj, "title_name", None) or getattr(obj, "ps_name", None) or f"#{getattr(obj, 'id', '?')}"


@dataclass(frozen=True)
class ResolvedContext:
    chat_id: int
    user_id: int
    is_group: bool
    object_id: Optional[int]
    title: Optional[str]
    requires_selection: bool = False


@dataclass(frozen=True)
class ContextResolver:
    settings: Settings
    objects_repo: ObjectsRepository
    groups_repo: GroupsRepository
    links_repo: ObjectsRepository  # same instance as objects_repo — see container.py
    user_contexts_repo: UserContextsRepository
    rbac: RBACService

    async def resolve(
        self,
        session: AsyncSession,
        chat_id: int,
        user_id: int,
        is_group: bool,
    ) -> ResolvedContext:
        if is_group:
            return await self._resolve_group(session, chat_id, user_id)
        return await self._resolve_private(session, chat_id, user_id)

    async def _resolve_group(
        self,
        session: AsyncSession,
        chat_id: int,
        user_id: int,
    ) -> ResolvedContext:
        # Objects linked to this group chat via ObjectGroupLink
        objects = await self.objects_repo.list_linked_objects(session, chat_id)
        if not objects:
            return ResolvedContext(
                chat_id=chat_id, user_id=user_id,
                is_group=True, object_id=None, title=None,
            )
        if len(objects) == 1:
            obj = objects[0]
            return ResolvedContext(
                chat_id=chat_id, user_id=user_id,
                is_group=True, object_id=obj.id, title=_display_name(obj),
            )
        # Multiple objects — check cached user selection (TTL-aware)
        now = datetime.now(timezone.utc)
        cached_id = await self.user_contexts_repo.get_selected_object_id(
            session, telegram_user_id=user_id, chat_id=chat_id, now=now
        )
        if cached_id is not None:
            matched = next((o for o in objects if o.id == cached_id), None)
            if matched:
                return ResolvedContext(
                    chat_id=chat_id, user_id=user_id,
                    is_group=True, object_id=matched.id, title=_display_name(matched),
                )
        logger.debug("context_requires_selection", chat_id=chat_id, user_id=user_id)
        return ResolvedContext(
            chat_id=chat_id, user_id=user_id,
            is_group=True, object_id=None, title=None, requires_selection=True,
        )

    async def _resolve_private(
        self,
        session: AsyncSession,
        chat_id: int,
        user_id: int,
    ) -> ResolvedContext:
        if not await self.rbac.is_allowed_private(session, user_id):
            logger.debug("private_access_denied", user_id=user_id)
            return ResolvedContext(
                chat_id=chat_id, user_id=user_id,
                is_group=False, object_id=None, title=None,
            )
        now = datetime.now(timezone.utc)
        cached_id = await self.user_contexts_repo.get_selected_object_id(
            session, telegram_user_id=user_id, chat_id=chat_id, now=now
        )
        if cached_id is not None:
            obj = await self.objects_repo.get_by_id(session, cached_id)
            if obj:
                return ResolvedContext(
                    chat_id=chat_id, user_id=user_id,
                    is_group=False, object_id=obj.id, title=_display_name(obj),
                )
        objects = await self.objects_repo.list(session)
        if not objects:
            return ResolvedContext(
                chat_id=chat_id, user_id=user_id,
                is_group=False, object_id=None, title=None,
            )
        if len(objects) == 1:
            obj = objects[0]
            return ResolvedContext(
                chat_id=chat_id, user_id=user_id,
                is_group=False, object_id=obj.id, title=_display_name(obj),
            )
        return ResolvedContext(
            chat_id=chat_id, user_id=user_id,
            is_group=False, object_id=None, title=None, requires_selection=True,
        )

    async def set_context(
        self,
        session: AsyncSession,
        user_id: int,
        chat_id: int,
        object_id: int,
    ) -> None:
        now = datetime.now(timezone.utc)
        ttl = self.settings.context_ttl_seconds
        expires_at = now + timedelta(seconds=ttl) if ttl > 0 else None
        await self.user_contexts_repo.set_selected_object(
            session,
            telegram_user_id=user_id,
            chat_id=chat_id,
            object_id=object_id,
            selected_at=now,
            expires_at=expires_at,
        )
