from __future__ import annotations

from typing import Any

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.core.logging import get_logger

logger = get_logger(__name__)


def _extract_command_and_args(text: str) -> tuple[str, list[str]]:
    t = (text or "").strip()
    if not t:
        return "", []
    parts = t.split()
    cmd = parts[0].lstrip("/").split("@")[0]
    return cmd, parts[1:]


def _parse_target_user_id(message: Message) -> int | None:
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user.id

    _cmd, args = _extract_command_and_args(message.text or "")
    if not args:
        return None
    try:
        return int(args[0])
    except ValueError:
        return None


def router(container: object) -> Router:  # type: ignore[type-arg]
    r = Router(name="superadmin")

    @r.message(Command("admin_list"))
    async def cmd_admin_list(message: Message, **kwargs: Any) -> None:
        session = kwargs["session"]
        role: str = kwargs.get("user_role", "user")
        if role != "superadmin":
            await message.answer("⛔ Доступ запрещён.")
            return

        admin_ids = await container.admins_repo.list(session)  # type: ignore[attr-defined]
        if not admin_ids:
            await message.answer("Администраторы не найдены.")
            return
        await message.answer("👑 Администраторы:\n" + "\n".join(f"• {uid}" for uid in admin_ids))

    @r.message(Command("admin_add"))
    async def cmd_admin_add(message: Message, **kwargs: Any) -> None:
        session = kwargs["session"]
        role: str = kwargs.get("user_role", "user")
        if role != "superadmin":
            await message.answer("⛔ Доступ запрещён.")
            return

        target_id = _parse_target_user_id(message)
        if target_id is None:
            # FIX: <telegram_user_id> -> [telegram_user_id]
            await message.answer("Формат: /admin_add [telegram_user_id] (или ответьте на сообщение пользователя).")
            return

        await container.admins_repo.add(session, target_id)  # type: ignore[attr-defined]
        await message.answer(f"✅ Администратор добавлен: {target_id}")
        logger.info("admin_added", actor=message.from_user.id if message.from_user else None, target=target_id)

    @r.message(Command("admin_del"))
    async def cmd_admin_del(message: Message, **kwargs: Any) -> None:
        session = kwargs["session"]
        role: str = kwargs.get("user_role", "user")
        if role != "superadmin":
            await message.answer("⛔ Доступ запрещён.")
            return

        target_id = _parse_target_user_id(message)
        if target_id is None:
            # FIX: <telegram_user_id> -> [telegram_user_id]
            await message.answer("Формат: /admin_del [telegram_user_id] (или ответьте на сообщение пользователя).")
            return

        removed = await container.admins_repo.remove(session, target_id)  # type: ignore[attr-defined]
        if removed:
            await message.answer(f"✅ Администратор удалён: {target_id}")
            logger.info("admin_removed", actor=message.from_user.id if message.from_user else None, target=target_id)
        else:
            await message.answer(f"ℹ️ Пользователь {target_id} не был администратором.")

    return r
