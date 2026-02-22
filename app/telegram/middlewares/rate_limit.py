from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject, Update

from app.core.module_registry import ModuleRegistry
from app.services.rate_limiter import RateLimiter


class RateLimitMiddleware(BaseMiddleware):
    def __init__(self, rate_limiter: RateLimiter, registry: ModuleRegistry) -> None:
        self.rate_limiter = rate_limiter
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
            return await handler(event, data)

        text: str = message.text or ""
        if not text.startswith("/"):
            return await handler(event, data)

        command = text.lstrip("/").split("@")[0].split()[0]

        # /materials is a start command; module handles cooldown after confirm.
        if command == "materials":
            return await handler(event, data)

        spec = self.registry.get_command_spec(command)

        if spec is None:
            return await handler(event, data)
        if spec.rate_limit_exempt:
            return await handler(event, data)
        if not spec.rate_limited:
            return await handler(event, data)

        session = data["session"]
        user_id: int = message.from_user.id
        is_group: bool = message.chat.type in ("group", "supergroup")

        scope_type = "chat" if is_group else "user"
        scope_id = message.chat.id if is_group else user_id

        is_allowed, wait_seconds = await self.rate_limiter.check_and_touch(
            session,
            scope_type=scope_type,
            scope_id=scope_id,
        )
        if not is_allowed:
            now = datetime.now().astimezone()
            until = now + timedelta(seconds=int(wait_seconds))
            minutes = max(1, (wait_seconds + 59) // 60)
            await message.answer(
                "⏳ Лимит заявок. "
                f"Повторите через {minutes} мин. (до {until:%H:%M})."
            )
            return None

        return await handler(event, data)
