from __future__ import annotations

import asyncio
import io
import re
from datetime import date, datetime
from typing import Any

import openpyxl
from aiogram import Router
from aiogram.enums import ChatType
from aiogram.filters import Command
from aiogram.types import Message
from pydantic import EmailStr, ValidationError

from app.core.logging import get_logger

logger = get_logger(__name__)


def _extract_command_and_args(text: str) -> tuple[str, list[str]]:
    t = (text or "").strip()
    if not t:
        return "", []
    parts = t.split()
    cmd = parts[0].lstrip("/").split("@")[0]
    return cmd, parts[1:]


def _parse_int_arg(args: list[str], idx: int = 0) -> int | None:
    if len(args) <= idx:
        return None
    try:
        return int(args[idx])
    except ValueError:
        return None


def _parse_target_user_id(message: Message) -> int | None:
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user.id
    _cmd, args = _extract_command_and_args(message.text or "")
    return _parse_int_arg(args, 0)


def _is_admin_role(role: str) -> bool:
    return role in ("admin", "superadmin")


_HEADER_SYNONYMS: dict[str, str] = {
    "№ пс": "ps_number",
    "номер пс": "ps_number",
    "пс №": "ps_number",
    "пс": "ps_number",
    "ps": "ps_number",
    "ps_number": "ps_number",

    "наименование пс": "ps_name",
    "название пс": "ps_name",
    "пс наименование": "ps_name",
    "ps_name": "ps_name",

    "вид работ": "work_type",
    "work_type": "work_type",

    "наименование объекта": "title_name",
    "объект": "title_name",
    "title_name": "title_name",

    "адрес": "address",
    "address": "address",

    "договор": "contract_number",
    "№ договора": "contract_number",
    "номер договора": "contract_number",
    "contract_number": "contract_number",

    "заявка": "request_number",
    "№ заявки": "request_number",
    "номер заявки": "request_number",
    "request_number": "request_number",

    "заказчик": "customer",
    "customer": "customer",

    "подрядчик": "extra.contractor",
    "contractor": "extra.contractor",
}


def _norm_header(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def _cell_to_date(v: Any) -> date | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, str):
        t = v.strip()
        for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(t, fmt).date()
            except ValueError:
                continue
    return None


async def _download_document_bytes(message: Message) -> tuple[str, bytes] | None:
    doc = message.document
    if doc is None and message.reply_to_message is not None:
        doc = message.reply_to_message.document
    if doc is None:
        return None

    bot = message.bot
    tg_file = await bot.get_file(doc.file_id)
    buf = io.BytesIO()
    await bot.download_file(tg_file.file_path, destination=buf)
    return (doc.file_name or "objects.xlsx", buf.getvalue())


def _parse_objects_xlsx(content: bytes) -> list[dict[str, Any]]:
    wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
    ws = wb.active

    header_row_idx: int | None = None
    headers: dict[int, str] = {}

    for r in range(1, min(10, ws.max_row) + 1):
        row_vals = [ws.cell(row=r, column=c).value for c in range(1, ws.max_column + 1)]
        if not any(v is not None and str(v).strip() for v in row_vals):
            continue
        header_row_idx = r
        for c, v in enumerate(row_vals, start=1):
            if v is None:
                continue
            h = _norm_header(str(v))
            if h:
                headers[c] = h
        break

    if header_row_idx is None or not headers:
        return []

    records: list[dict[str, Any]] = []
    for r in range(header_row_idx + 1, ws.max_row + 1):
        values = {c: ws.cell(row=r, column=c).value for c in headers.keys()}
        if not any(v is not None and str(v).strip() for v in values.values()):
            continue

        fields: dict[str, Any] = {}
        extra: dict[str, Any] = {}

        for c, raw_h in headers.items():
            v = values.get(c)
            if v is None:
                continue
            h = _norm_header(raw_h)
            key = _HEADER_SYNONYMS.get(h)
            if key is None:
                extra[h] = str(v).strip() if isinstance(v, str) else v
                continue

            if key.startswith("extra."):
                ex_key = key.split(".", 1)[1]
                extra[ex_key] = str(v).strip() if isinstance(v, str) else v
                continue

            if key.endswith("_start") or key.endswith("_end"):
                fields[key] = _cell_to_date(v)
                continue

            fields[key] = str(v).strip() if isinstance(v, str) else v

        if extra:
            fields["extra"] = extra

        records.append(fields)

    return records


def _dedup_key(fields: dict[str, Any]) -> str:
    ps_number = str(fields.get("ps_number") or "").strip()
    ps_name = str(fields.get("ps_name") or "").strip()
    address = str(fields.get("address") or "").strip()
    contract_number = str(fields.get("contract_number") or "").strip()

    base = "|".join([ps_number, ps_name, address, contract_number]).strip("|")
    base = re.sub(r"\s+", " ", base).lower()
    return base or (str(fields.get("title_name") or "").strip().lower() or "unknown")


def router(container: object) -> Router:  # type: ignore[type-arg]
    r = Router(name="admin")

    @r.message(Command("commands"))
    async def cmd_commands(message: Message, **kwargs: Any) -> None:
        role: str = kwargs.get("user_role", "user")
        if not _is_admin_role(role):
            await message.answer("⛔ Доступ запрещён.")
            return

        specs = container.registry.all_commands()  # type: ignore[attr-defined]
        admin_cmds = [s for s in specs if s.required_role in ("admin", "superadmin")]
        lines = ["📋 Админские команды:"]
        lines.extend([f"/{s.command} — {s.description}" for s in admin_cmds])
        await message.answer("\n".join(lines))

    @r.message(Command("recipient_email"))
    async def cmd_recipient_email(message: Message, **kwargs: Any) -> None:
        role: str = kwargs.get("user_role", "user")
        if not _is_admin_role(role):
            await message.answer("⛔ Доступ запрещён.")
            return

        session = kwargs["session"]
        _cmd, args = _extract_command_and_args(message.text or "")
        if not args:
            cur = await container.settings_service.get_recipient_email(session)  # type: ignore[attr-defined]
            await message.answer(f"📧 Текущий получатель: {cur or '—'}\nФормат: /recipient_email user@domain")
            return

        raw = args[0].strip()
        try:
            email = EmailStr(raw)
        except ValidationError:
            await message.answer("⚠️ Некорректный email. Формат: user@domain")
            return

        await container.settings_service.set_recipient_email(session, str(email))  # type: ignore[attr-defined]
        await message.answer(f"✅ Email получателя установлен: {email}")
        logger.info("recipient_email_set", actor=message.from_user.id if message.from_user else None, email=str(email))

    @r.message(Command("time"))
    async def cmd_time(message: Message, **kwargs: Any) -> None:
        role: str = kwargs.get("user_role", "user")
        if not _is_admin_role(role):
            await message.answer("⛔ Доступ запрещён.")
            return

        session = kwargs["session"]
        _cmd, args = _extract_command_and_args(message.text or "")
        if not args:
            cur = await container.settings_service.get_cooldown_minutes(session)  # type: ignore[attr-defined]
            await message.answer(f"⏱ Текущий cooldown: {cur} мин.\nФормат: /time 30")
            return

        try:
            minutes = int(args[0])
        except ValueError:
            await message.answer("⚠️ Некорректное число минут. Формат: /time 30")
            return

        await container.settings_service.set_cooldown_minutes(session, minutes)  # type: ignore[attr-defined]
        new_val = await container.settings_service.get_cooldown_minutes(session)  # type: ignore[attr-defined]
        await message.answer(f"✅ Cooldown установлен: {new_val} мин.")
        logger.info("cooldown_set", actor=message.from_user.id if message.from_user else None, minutes=new_val)

    @r.message(Command("object_list"))
    async def cmd_object_list(message: Message, **kwargs: Any) -> None:
        role: str = kwargs.get("user_role", "user")
        if not _is_admin_role(role):
            await message.answer("⛔ Доступ запрещён.")
            return

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

    @r.message(Command("object_add"))
    async def cmd_object_add(message: Message, **kwargs: Any) -> None:
        role: str = kwargs.get("user_role", "user")
        if not _is_admin_role(role):
            await message.answer("⛔ Доступ запрещён.")
            return

        text = (message.text or "")
        payload = text.split(maxsplit=1)
        if len(payload) < 2:
            await message.answer("Формат: /object_add <ps_number>; <ps_name>; <address (опц.)>")
            return

        parts = [p.strip() for p in payload[1].split(";") if p.strip()]
        if len(parts) < 2:
            await message.answer("Формат: /object_add <ps_number>; <ps_name>; <address (опц.)>")
            return

        ps_number, ps_name = parts[0], parts[1]
        address = parts[2] if len(parts) >= 3 else ""

        fields: dict[str, Any] = {
            "ps_number": ps_number,
            "ps_name": ps_name,
            "title_name": ps_name,
            "address": address,
            "extra": {},
        }
        dedup = _dedup_key(fields)

        session = kwargs["session"]
        obj, created = await container.objects_repo.upsert_by_dedup_key(session, dedup_key=dedup, fields=fields)  # type: ignore[attr-defined]
        await message.answer(
            f"✅ Объект {'добавлен' if created else 'обновлён'}: id={obj.id}\n"
            f"ПС: {obj.ps_number or '—'} {obj.ps_name or ''}\n"
            f"Адрес: {obj.address or '—'}"
        )

    @r.message(Command("object_del"))
    async def cmd_object_del(message: Message, **kwargs: Any) -> None:
        role: str = kwargs.get("user_role", "user")
        if not _is_admin_role(role):
            await message.answer("⛔ Доступ запрещён.")
            return

        _cmd, args = _extract_command_and_args(message.text or "")
        object_id = _parse_int_arg(args, 0)
        if object_id is None:
            await message.answer("Формат: /object_del <object_id>")
            return

        session = kwargs["session"]
        deleted = await container.objects_repo.delete(session, object_id)  # type: ignore[attr-defined]
        if deleted:
            await message.answer(f"✅ Объект удалён: {object_id}")
        else:
            await message.answer(f"ℹ️ Объект не найден: {object_id}")

    @r.message(Command("object_import"))
    async def cmd_object_import(message: Message, **kwargs: Any) -> None:
        role: str = kwargs.get("user_role", "user")
        if not _is_admin_role(role):
            await message.answer("⛔ Доступ запрещён.")
            return

        dl = await _download_document_bytes(message)
        if dl is None:
            await message.answer(
                "📥 Пришлите Excel-файл (.xlsx) с объектами и выполните /object_import "
                "в подписи к файлу или ответом на сообщение с файлом."
            )
            return

        file_name, content = dl
        await message.answer("⏳ Импортирую объекты из Excel...")

        records = await asyncio.to_thread(_parse_objects_xlsx, content)
        if not records:
            await message.answer("⚠️ Не удалось распознать таблицу в Excel (нет заголовков/строк).")
            return

        session = kwargs["session"]

        created = 0
        updated = 0
        errors = 0

        for fields in records:
            try:
                dedup = _dedup_key(fields)
                _obj, was_created = await container.objects_repo.upsert_by_dedup_key(  # type: ignore[attr-defined]
                    session,
                    dedup_key=dedup,
                    fields=fields,
                )
                if was_created:
                    created += 1
                else:
                    updated += 1
            except Exception as exc:
                errors += 1
                logger.error("object_import_row_failed", file=file_name, error=str(exc)[:200])

        await message.answer(
            "✅ Импорт завершён.\n"
            f"Файл: {file_name}\n"
            f"Строк обработано: {len(records)}\n"
            f"Создано: {created}\n"
            f"Обновлено: {updated}\n"
            f"Ошибок: {errors}"
        )

    @r.message(Command("group_list"))
    async def cmd_group_list(message: Message, **kwargs: Any) -> None:
        role: str = kwargs.get("user_role", "user")
        if not _is_admin_role(role):
            await message.answer("⛔ Доступ запрещён.")
            return

        session = kwargs["session"]

        chat_id = message.chat.id if message.chat.type in (ChatType.GROUP, ChatType.SUPERGROUP) else None
        links = await container.objects_repo.list_group_links(session, chat_id=chat_id)  # type: ignore[attr-defined]
        if not links:
            await message.answer("Привязки не найдены.")
            return

        text_lines = ["📋 Привязки (object_id → chat_id):"]
        text_lines.extend([f"• {obj_id} → {gid}" for obj_id, gid in links])
        await message.answer("\n".join(text_lines))

    @r.message(Command("group_add"))
    async def cmd_group_add(message: Message, **kwargs: Any) -> None:
        role: str = kwargs.get("user_role", "user")
        if not _is_admin_role(role):
            await message.answer("⛔ Доступ запрещён.")
            return
        if message.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
            await message.answer("⚠️ /group_add доступна только в группе/супергруппе.")
            return

        _cmd, args = _extract_command_and_args(message.text or "")
        object_id = _parse_int_arg(args, 0)
        if object_id is None:
            await message.answer("Формат: /group_add <object_id> (в группе).")
            return

        session = kwargs["session"]
        obj = await container.objects_repo.get_by_id(session, object_id)  # type: ignore[attr-defined]
        if not obj:
            await message.answer(f"⚠️ Объект не найден: {object_id}")
            return

        await container.objects_repo.link_group(session, object_id=object_id, chat_id=message.chat.id)  # type: ignore[attr-defined]
        await message.answer(f"✅ Группа привязана к объекту {object_id} (chat_id={message.chat.id})")

    @r.message(Command("group_del"))
    async def cmd_group_del(message: Message, **kwargs: Any) -> None:
        role: str = kwargs.get("user_role", "user")
        if not _is_admin_role(role):
            await message.answer("⛔ Доступ запрещён.")
            return
        if message.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
            await message.answer("⚠️ /group_del доступна только в группе/супергруппе.")
            return

        _cmd, args = _extract_command_and_args(message.text or "")
        object_id = _parse_int_arg(args, 0)
        if object_id is None:
            await message.answer("Формат: /group_del <object_id> (в группе).")
            return

        session = kwargs["session"]
        removed = await container.objects_repo.unlink_group(session, object_id=object_id, chat_id=message.chat.id)  # type: ignore[attr-defined]
        if removed:
            await message.answer(f"✅ Привязка удалена: object_id={object_id} ↔ chat_id={message.chat.id}")
        else:
            await message.answer("ℹ️ Привязка не найдена.")

    @r.message(Command("user_list"))
    async def cmd_user_list(message: Message, **kwargs: Any) -> None:
        role: str = kwargs.get("user_role", "user")
        if not _is_admin_role(role):
            await message.answer("⛔ Доступ запрещён.")
            return

        session = kwargs["session"]
        users = await container.users_repo.list_allowed_private(session)  # type: ignore[attr-defined]
        if not users:
            await message.answer("Список пуст.")
            return
        await message.answer(
            "👤 Разрешённые (личка):\n"
            + "\n".join(f"• {u.telegram_user_id}" for u in users)
        )

    @r.message(Command("user_add"))
    async def cmd_user_add(message: Message, **kwargs: Any) -> None:
        role: str = kwargs.get("user_role", "user")
        if not _is_admin_role(role):
            await message.answer("⛔ Доступ запрещён.")
            return

        target_id = _parse_target_user_id(message)
        if target_id is None:
            await message.answer("Формат: /user_add <telegram_user_id> (или ответьте на сообщение пользователя).")
            return

        session = kwargs["session"]
        await container.users_repo.set_allowed_private(session, target_id, True)  # type: ignore[attr-defined]
        await message.answer(f"✅ Пользователь разрешён в личном чате: {target_id}")

    @r.message(Command("user_del"))
    async def cmd_user_del(message: Message, **kwargs: Any) -> None:
        role: str = kwargs.get("user_role", "user")
        if not _is_admin_role(role):
            await message.answer("⛔ Доступ запрещён.")
            return

        target_id = _parse_target_user_id(message)
        if target_id is None:
            await message.answer("Формат: /user_del <telegram_user_id> (или ответьте на сообщение пользователя).")
            return

        session = kwargs["session"]
        await container.users_repo.set_allowed_private(session, target_id, False)  # type: ignore[attr-defined]
        await message.answer(f"✅ Пользователь запрещён в личном чате: {target_id}")

    return r
