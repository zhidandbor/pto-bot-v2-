from __future__ import annotations

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
        spec = self.registry.get_command(command)
        if spec is None or getattr(spec, "rate_limit_exempt", False):
            return await handler(event, data)

        session = data["session"]
        user_id: int = message.from_user.id

        is_allowed, wait_seconds = await self.rate_limiter.check_and_touch(
            session,
            scope_type="user",
            scope_id=user_id,
        )
        if not is_allowed:
            minutes = max(1, (wait_seconds + 59) // 60)
            await message.answer(f"\u23f3 Лимит заявок. Повторите через {minutes} мин.")
            return None

        return await handler(event, data)
