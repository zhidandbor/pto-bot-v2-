from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, Update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.module_registry import ModuleRegistry
from app.services.rbac import RBACService

_ROLE_ORDER: dict[str, int] = {"superadmin": 3, "admin": 2, "user": 1, "blocked": 0}


async def _resolve_role(
    rbac: RBACService,
    session: AsyncSession,
    user_id: int,
    is_group: bool,
) -> str:
    if rbac.is_superadmin(user_id):
        return "superadmin"
    if await rbac.is_admin(session, user_id):
        return "admin"
    # In groups all participants are treated as regular users.
    # In private chats only explicitly allowed users get "user" role.
    if is_group or await rbac.is_allowed_private(session, user_id):
        return "user"
    return "blocked"


class RBACMiddleware(BaseMiddleware):
    def __init__(self, rbac: RBACService, registry: ModuleRegistry) -> None:
        self.rbac = rbac
        self.registry = registry

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, Update):
            data.setdefault("user_role", "user")
            return await handler(event, data)

        session: AsyncSession = data["session"]

        # --- callback_query path ---
        # callback_query MUST also go through RBAC; previously it defaulted to "user".
        if event.callback_query is not None:
            cq: CallbackQuery = event.callback_query
            if cq.from_user is not None:
                chat_type = "private"
                if cq.message is not None:
                    chat_type = cq.message.chat.type
                is_group_cq = chat_type in ("group", "supergroup")
                role = await _resolve_role(self.rbac, session, cq.from_user.id, is_group_cq)
                data["user_role"] = role
            else:
                data["user_role"] = "blocked"
            return await handler(event, data)

        # --- message path ---
        message: Message | None = event.message
        if message is None or message.from_user is None:
            data.setdefault("user_role", "user")
            return await handler(event, data)

        user_id: int = message.from_user.id
        is_group: bool = message.chat.type in ("group", "supergroup")
        role = await _resolve_role(self.rbac, session, user_id, is_group)
        data["user_role"] = role

        text: str = message.text or ""
        if text.startswith("/"):
            command = text.lstrip("/").split("@")[0].split()[0]
            spec = self.registry.get_command_spec(command)  # was: get_command()
            if spec is not None:
                required: str = spec.required_role  # was: spec.role
                if _ROLE_ORDER.get(role, 0) < _ROLE_ORDER.get(required, 1):
                    await message.answer("\u26d4 Недостаточно прав.")
                    return None

        return await handler(event, data)
