from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message


def router(container: object) -> Router:  # type: ignore[type-arg]
    r = Router(name="admin")

    @r.message(Command("object_list"))
    async def cmd_object_list(message: Message, **kwargs: object) -> None:
        session = kwargs["session"]
        objects = await container.objects_repo.get_all(session)  # type: ignore[attr-defined]
        if not objects:
            await message.answer("Объекты не найдены.")
            return
        await message.answer("\U0001f4cb Объекты:\n" + "\n".join(f"\u2022 {o.title}" for o in objects))

    @r.message(Command("group_list"))
    async def cmd_group_list(message: Message, **kwargs: object) -> None:
        session = kwargs["session"]
        groups = await container.groups_repo.get_all(session)  # type: ignore[attr-defined]
        if not groups:
            await message.answer("Привязки не найдены.")
            return
        await message.answer("\U0001f4cb Привязки:\n" + "\n".join(f"\u2022 {g}" for g in groups))

    @r.message(Command("user_list"))
    async def cmd_user_list(message: Message, **kwargs: object) -> None:
        session = kwargs["session"]
        users = await container.users_repo.get_all_allowed(session)  # type: ignore[attr-defined]
        if not users:
            await message.answer("Список пуст.")
            return
        await message.answer("\U0001f464 Разрешённые:\n" + "\n".join(f"\u2022 {u.user_id}" for u in users))

    async def _not_implemented(message: Message, **kwargs: object) -> None:
        cmd = (message.text or "").lstrip("/").split("@")[0].split()[0]
        await message.answer(f"\u2699\ufe0f /{cmd} — в разработке.")

    for _cmd in (
        "object_add", "object_del", "object_import",
        "group_add", "group_del",
        "user_add", "user_del",
        "recipient_email", "time",
    ):
        r.message(Command(_cmd))(_not_implemented)

    return r
