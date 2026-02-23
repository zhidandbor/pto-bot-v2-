from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject, Update
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.core.module_registry import ModuleRegistry
from app.services.context_resolver import ContextResolver


def _display_name(obj: object) -> str:
    return getattr(obj, "title_name", None) or getattr(obj, "ps_name", None) or f"#{getattr(obj, 'id', '?')}"


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

        # --- FIX BUG-1: skip context resolution for commands that don't require
        # object context. Without this check, admin/superadmin commands (/admin_add,
        # /user_add, /object_add, etc.) were intercepted by the object-selector logic
        # and either silently blocked or caused an exception when no objects existed
        # (Telegram rejects empty inline keyboards), which ErrorHandlerMiddleware
        # converted into "\u26a0\ufe0f \u0412\u043d\u0443\u0442\u0440\u0435\u043d\u043d\u0430\u044f \u043e\u0448\u0438\u0431\u043a\u0430". ---
        text: str = message.text or ""
        if text.startswith("/"):
            command = text.lstrip("/").split("@")[0].split()[0]
            spec = self.registry.get_command_spec(command)
            if spec is not None and not spec.requires_object_context:
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
            if is_group:
                objects = await self.resolver.objects_repo.list_linked_objects(session, chat.id)
            else:
                objects = await self.resolver.objects_repo.list(session)

            # Guard: Telegram API rejects empty inline keyboards.
            # If no objects are configured yet, pass through to the handler.
            if not objects:
                return await handler(event, data)

            builder = InlineKeyboardBuilder()
            for obj in objects:
                builder.button(
                    text=_display_name(obj),
                    callback_data=f"ctx_select:{obj.id}:{chat.id}",
                )
            builder.adjust(1)
            await message.answer("\U0001f4cb \u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u043e\u0431\u044a\u0435\u043a\u0442:", reply_markup=builder.as_markup())
            return None

        return await handler(event, data)
