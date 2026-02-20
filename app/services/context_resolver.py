from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.logging import get_logger
from app.db.repositories.groups import GroupsRepository
from app.db.repositories.objects import ObjectsRepository
from app.db.repositories.user_contexts import UserContextsRepository
from app.services.rbac import RBACService

logger = get_logger(__name__)


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
        objects = await self.groups_repo.get_objects_for_chat(session, chat_id)
        if not objects:
            return ResolvedContext(
                chat_id=chat_id, user_id=user_id,
                is_group=True, object_id=None, title=None,
            )
        if len(objects) == 1:
            obj = objects[0]
            return ResolvedContext(
                chat_id=chat_id, user_id=user_id,
                is_group=True, object_id=obj.id, title=obj.title,
            )
        # Multiple objects — check cached user selection
        cached = await self.user_contexts_repo.get(
            session, user_id=user_id, chat_id=chat_id
        )
        if cached is not None:
            matched = next((o for o in objects if o.id == cached.object_id), None)
            if matched:
                return ResolvedContext(
                    chat_id=chat_id, user_id=user_id,
                    is_group=True, object_id=matched.id, title=matched.title,
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
        cached = await self.user_contexts_repo.get(
            session, user_id=user_id, chat_id=chat_id
        )
        if cached is not None:
            obj = await self.objects_repo.get_by_id(session, cached.object_id)
            if obj:
                return ResolvedContext(
                    chat_id=chat_id, user_id=user_id,
                    is_group=False, object_id=obj.id, title=obj.title,
                )
        objects = await self.objects_repo.get_all(session)
        if not objects:
            return ResolvedContext(
                chat_id=chat_id, user_id=user_id,
                is_group=False, object_id=None, title=None,
            )
        if len(objects) == 1:
            obj = objects[0]
            return ResolvedContext(
                chat_id=chat_id, user_id=user_id,
                is_group=False, object_id=obj.id, title=obj.title,
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
        await self.user_contexts_repo.set(
            session, user_id=user_id, chat_id=chat_id, object_id=object_id
        )
