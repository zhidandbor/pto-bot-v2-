from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject, Update
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.core.module_registry import ModuleRegistry
from app.services.context_resolver import ContextResolver


class ContextResolverMiddleware(BaseMiddleware):
    def __init__(self, resolver: ContextResolver, registry: ModuleRegistry) -> None:
        self.resolver = resolver
        self.registry = registry

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        message: Message | None = None
        if isinstance(event, Update):
            message = event.message

        if message is None or message.from_user is None:
            data["context"] = None
            return await handler(event, data)

        session = data["session"]
        chat = message.chat
        user = message.from_user
        is_group: bool = chat.type in ("group", "supergroup")

        ctx = await self.resolver.resolve(
            session, chat_id=chat.id, user_id=user.id, is_group=is_group
        )
        data["context"] = ctx

        if ctx.requires_selection:
            objects = await self.resolver.objects_repo.get_all(session)
            builder = InlineKeyboardBuilder()
            for obj in objects:
                builder.button(
                    text=obj.title,
                    callback_data=f"ctx_select:{obj.id}:{chat.id}",
                )
            builder.adjust(1)
            await message.answer("\U0001f4cb Выберите объект:", reply_markup=builder.as_markup())
            return None

        return await handler(event, data)
