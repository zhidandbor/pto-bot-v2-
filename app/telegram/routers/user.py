from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message


def router(container: object) -> Router:  # type: ignore[type-arg]
    r = Router(name="user")

    @r.message(Command("start", "sart"))
    async def cmd_start(message: Message, **kwargs: object) -> None:
        session = kwargs["session"]
        role: str = kwargs.get("user_role", "user")  # type: ignore[assignment]
        text = await container.help_service.get_start_text(session, role)  # type: ignore[attr-defined]
        await message.answer(text)

    @r.message(Command("help"))
    async def cmd_help(message: Message, **kwargs: object) -> None:
        session = kwargs["session"]
        role: str = kwargs.get("user_role", "user")  # type: ignore[assignment]
        text = await container.help_service.get_help_text(session, role)  # type: ignore[attr-defined]
        await message.answer(text)

    @r.message(Command("object_search"))
    async def cmd_object_search(message: Message, **kwargs: object) -> None:
        await message.answer("\U0001f50d Введите название объекта для поиска.")

    return r
