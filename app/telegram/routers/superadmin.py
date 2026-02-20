from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message


def router(container: object) -> Router:  # type: ignore[type-arg]
    r = Router(name="superadmin")

    @r.message(Command("admin_list"))
    async def cmd_admin_list(message: Message, **kwargs: object) -> None:
        session = kwargs["session"]
        admins = await container.admins_repo.get_all(session)  # type: ignore[attr-defined]
        if not admins:
            await message.answer("Администраторы не найдены.")
            return
        await message.answer(
            "\U0001f451 Администраторы:\n" + "\n".join(f"\u2022 {a.user_id}" for a in admins)
        )

    async def _not_implemented(message: Message, **kwargs: object) -> None:
        cmd = (message.text or "").lstrip("/").split("@")[0].split()[0]
        await message.answer(f"\u2699\ufe0f /{cmd} — в разработке.")

    for _cmd in ("admin_add", "admin_del"):
        r.message(Command(_cmd))(_not_implemented)

    return r
