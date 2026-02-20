from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update


class ErrorHandlerMiddleware(BaseMiddleware):
    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        try:
            return await handler(event, data)
        except Exception as exc:
            self.logger.exception(
                "unhandled_bot_error",
                error=str(exc),
                update_id=getattr(event, "update_id", None),
            )
            if isinstance(event, Update) and event.message:
                try:
                    await event.message.answer("\u26a0\ufe0f Внутренняя ошибка. Попробуйте позже.")
                except Exception:
                    pass
            return None
