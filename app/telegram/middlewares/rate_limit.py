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
        spec = self.registry.get_command_spec(command)  # was: get_command()

        if spec is None:
            # Unknown command — not registered, no rate limit applied.
            return await handler(event, data)
        if spec.rate_limit_exempt:
            # Absolute exemption (e.g. /knowledge).
            return await handler(event, data)
        if not spec.rate_limited:
            # Command is not flagged as a rate-limited operation
            # (e.g. /help, /object_list, admin config commands).
            return await handler(event, data)

        session = data["session"]
        user_id: int = message.from_user.id
        is_group: bool = message.chat.type in ("group", "supergroup")

        # Group: one shared cooldown per chat (all members share the quota).
        # Private: individual cooldown per user.
        scope_type = "chat" if is_group else "user"
        scope_id = message.chat.id if is_group else user_id

        is_allowed, wait_seconds = await self.rate_limiter.check_and_touch(
            session,
            scope_type=scope_type,
            scope_id=scope_id,
        )
        if not is_allowed:
            minutes = max(1, (wait_seconds + 59) // 60)
            await message.answer(f"\u23f3 Лимит заявок. Повторите через {minutes} мин.")
            return None

        return await handler(event, data)
