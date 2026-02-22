from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message


def router(container: object) -> Router:  # type: ignore[type-arg]
    r = Router(name="admin")

    @r.message(Command("object_list"))
    async def cmd_object_list(message: Message, **kwargs: object) -> None:
        session = kwargs["session"]
        objects = await container.objects_repo.list(session)  # type: ignore[attr-defined]
        if not objects:
            await message.answer("Объекты не найдены.")
            return

        lines: list[str] = []
        for o in objects:
            title = o.ps_name or o.title_name or o.address or o.dedup_key
            lines.append(f"• {o.id} — {title}")

        await message.answer("📋 Объекты:\n" + "\n".join(lines))

    @r.message(Command("group_list"))
    async def cmd_group_list(message: Message, **kwargs: object) -> None:
        session = kwargs["session"]

        # В группе показываем привязки только этой группы, в личке — все.
        chat_type = message.chat.type
        chat_id = message.chat.id if chat_type in ("group", "supergroup") else None

        links = await container.objects_repo.list_group_links(session, chat_id=chat_id)  # type: ignore[attr-defined]
        if not links:
            await message.answer("Привязки не найдены.")
            return

        text_lines = ["📋 Привязки (object_id → chat_id):"]
        text_lines.extend([f"• {obj_id} → {gid}" for obj_id, gid in links])
        await message.answer("\n".join(text_lines))

    @r.message(Command("user_list"))
    async def cmd_user_list(message: Message, **kwargs: object) -> None:
        session = kwargs["session"]
        users = await container.users_repo.list_allowed_private(session)  # type: ignore[attr-defined]
        if not users:
            await message.answer("Список пуст.")
            return
        await message.answer(
            "👤 Разрешённые (личка):\n"
            + "\n".join(f"• {u.telegram_user_id}" for u in users)
        )

    async def _not_implemented(message: Message, **kwargs: object) -> None:
        cmd = (message.text or "").lstrip("/").split("@")[0].split()[0]
        await message.answer(f"⚙️ /{cmd} — в разработке.")

    for _cmd in (
        "object_add", "object_del", "object_import",
        "group_add", "group_del",
        "user_add", "user_del",
        "recipient_email", "time",
    ):
        r.message(Command(_cmd))(_not_implemented)

    return r
