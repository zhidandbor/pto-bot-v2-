from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message


def router(container: object) -> Router:  # type: ignore[type-arg]
    r = Router(name="superadmin")

    @r.message(Command("admin_list"))
    async def cmd_admin_list(message: Message, **kwargs: object) -> None:
        session = kwargs["session"]
        admin_ids = await container.admins_repo.list(session)  # type: ignore[attr-defined]
        if not admin_ids:
            await message.answer("Администраторы не найдены.")
            return
        await message.answer("👑 Администраторы:\n" + "\n".join(f"• {uid}" for uid in admin_ids))

    async def _not_implemented(message: Message, **kwargs: object) -> None:
        cmd = (message.text or "").lstrip("/").split("@")[0].split()[0]
        await message.answer(f"⚙️ /{cmd} — в разработке.")

    for _cmd in ("admin_add", "admin_del"):
        r.message(Command(_cmd))(_not_implemented)

    return r
