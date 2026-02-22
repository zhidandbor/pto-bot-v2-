from __future__ import annotations

import asyncio
import secrets
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import NamedTuple

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.logging import get_logger
from app.db.repositories.materials import MaterialsRepository
from app.db.repositories.objects import ObjectsRepository
from app.db.repositories.rate_limits import RateLimitsRepository
from app.modules.materials.email_dispatcher import MaterialsEmailDispatcher
from app.modules.materials.excel import build_file_name, fill_excel_template
from app.modules.materials.parser import parse_materials_message
from app.modules.materials.schemas import MaterialDraft, MaterialLine
from app.services.settings_service import SettingsService

logger = get_logger(__name__)

_MAT_SCOPE = "mat_chat"


def _new_draft_id() -> str:
    return secrets.token_hex(6)


class PreviewResult(NamedTuple):
    draft_id: str
    preview_text: str
    hard_error: str


class ConfirmResult(NamedTuple):
    ok: bool
    message: str
    keep_keyboard: bool = False


def _build_obj_data(obj: object) -> dict:  # type: ignore[type-arg]
    work_period = ""
    if getattr(obj, "work_start", None):
        start = obj.work_start.strftime("%d.%m.%Y")  # type: ignore[union-attr]
        end = obj.work_end.strftime("%d.%m.%Y") if getattr(obj, "work_end", None) else ""  # type: ignore[union-attr]
        work_period = f"{start} — {end}" if end else start
    extra: dict = getattr(obj, "extra", {}) or {}  # type: ignore[type-arg]
    return {
        "ps_name": getattr(obj, "ps_name", "") or "",
        "contractor": extra.get("contractor", ""),
        "work_type": getattr(obj, "work_type", "") or "",
        "contract_number": getattr(obj, "contract_number", "") or "",
        "work_period": work_period,
        "customer": getattr(obj, "customer", "") or "",
        "address": getattr(obj, "address", "") or "",
    }


@dataclass(frozen=True)
class MaterialsService:
    session_factory: async_sessionmaker  # type: ignore[type-arg]
    materials_repo: MaterialsRepository
    objects_repo: ObjectsRepository
    rate_limits_repo: RateLimitsRepository
    settings_service: SettingsService
    email_dispatcher: MaterialsEmailDispatcher

    async def check_cooldown(self, *, scope_id: int) -> tuple[bool, int]:
        async with self.session_factory() as session:
            cooldown_minutes = await self.settings_service.get_cooldown_minutes(session)
            if cooldown_minutes <= 0:
                return True, 0
            row = await self.rate_limits_repo.get(session, scope_type=_MAT_SCOPE, scope_id=scope_id)
            if not row:
                return True, 0

            now = datetime.now(timezone.utc)
            last_at = row.last_request_at
            if last_at.tzinfo is None:
                last_at = last_at.replace(tzinfo=timezone.utc)
            else:
                last_at = last_at.astimezone(timezone.utc)
            next_allowed = last_at + timedelta(minutes=cooldown_minutes)
            if now < next_allowed:
                return False, int((next_allowed - now).total_seconds())
            return True, 0

    async def _resolve_private_input(
        self,
        *,
        session: object,
        text: str,
    ) -> tuple[object | None, str, str]:
        """Return (obj, lines_text, hard_error)."""
        raw = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if not raw:
            return None, "", "Сообщение пустое."

        if len(raw) >= 2:
            found = await self.objects_repo.search(session, raw[0], limit=1)  # type: ignore[arg-type]
            if not found:
                return None, "", (
                    "⚠️ В личном чате нужно указать объект первой строкой.\n\n"
                    "Пример:\nПС 55\nуголок г/к (50х50х5, L=6 м) - 0,156 т"
                )
            return found[0], "\n".join(raw[1:]), ""

        # Если реально прилетела одна строка — корректно обработать можно только 1 позицию.
        # Для списков из 2+ позиций без \n границы строк восстановить невозможно.
        one = raw[0]
        words = one.split()
        max_prefix = min(6, max(2, len(words) - 1))

        for n in range(max_prefix, 1, -1):
            cand = " ".join(words[:n]).strip()
            rest = " ".join(words[n:]).strip()
            if not rest:
                continue
            found = await self.objects_repo.search(session, cand, limit=3)  # type: ignore[arg-type]
            if not found:
                continue
            pr = parse_materials_message(rest)
            if pr.lines and len(pr.lines) == 1:
                return found[0], rest, ""

        return None, "", (
            "⚠️ Не удалось разобрать сообщение.\n\n"
            "В личном чате нужно отправить объект первой строкой, а материалы — со 2-й строки, "
            "каждый материал с новой строки.\n\n"
            "Пример:\nПС 55\nуголок г/к (50х50х5, L=6 м) - 0,156 т"
        )

    async def build_preview(
        self,
        *,
        text: str,
        chat_id: int,
        telegram_user_id: int,
        user_full_name: str | None,
        is_private: bool,
    ) -> PreviewResult:
        async with self.session_factory() as session:
            async with session.begin():
                obj = None
                lines_text = text

                if is_private:
                    obj, lines_text, hard_error = await self._resolve_private_input(session=session, text=text)  # type: ignore[arg-type]
                    if hard_error:
                        return PreviewResult("", "", hard_error)
                else:
                    linked = await self.objects_repo.list_linked_objects(session, chat_id)
                    if linked:
                        obj = linked[0]

                parse_result = parse_materials_message(lines_text)
                if not parse_result.lines:
                    err_detail = "\n".join(f"  • {e}" for e in parse_result.errors[:5])
                    return PreviewResult(
                        "",
                        "",
                        "⚠️ Не удалось распознать позиции заявки.\n\n"
                        "Проверьте формат строк:\n[Имя] ([Тип]) - [Количество] [Единицы]\n\n"
                        "Пример:\nуголок г/к (50х50х5, L=6 м) - 0,156 т"
                        + (f"\n\nОшибки:\n{err_detail}" if err_detail else ""),
                    )

                recipient_email = await self.settings_service.get_recipient_email(session)

                today = date.today()
                ps_number = (
                    getattr(obj, "ps_number", None)
                    or getattr(obj, "ps_name", None)
                    or "???"
                ) if obj else "???"
                draft_id = _new_draft_id()

                await self.materials_repo.create_request(
                    session,
                    draft_id=draft_id,
                    chat_id=chat_id if not is_private else None,
                    telegram_user_id=telegram_user_id,
                    object_id=getattr(obj, "id", None) if obj else None,
                    ps_number=ps_number,
                    request_date=today,
                    counter=0,
                    request_number=None,
                    recipient_email=recipient_email,
                    user_full_name=user_full_name,
                    lines=[ln.to_dict() for ln in parse_result.lines],
                )

                object_name = (
                    getattr(obj, "title_name", None)
                    or getattr(obj, "ps_name", None)
                    or ps_number
                ) if obj else ps_number

                lines_display = "\n".join(ln.display() for ln in parse_result.lines)
                preview = (
                    "📦 Заявка на материалы — ПРЕДПРОСМОТР\n\n"
                    f"Объект: {object_name}\n"
                    f"ПС: {ps_number}\n"
                    f"Дата: {today.strftime('%d.%m.%Y')}\n\n"
                    f"Позиции:\n{lines_display}\n\n"
                    "Проверьте список. Если всё верно — нажмите «✅ Подтвердить»."
                )
                if parse_result.errors:
                    preview += (
                        f"\n\n⚠️ Пропущено строк с ошибками ({len(parse_result.errors)}):\n"
                        + "\n".join(f"  • {e}" for e in parse_result.errors[:3])
                    )
                if parse_result.skipped:
                    preview += (
                        f"\n⚠️ Превышен лимит 25 позиций "
                        f"({parse_result.skipped} строк не вошло)."
                    )

                logger.info(
                    "materials_draft_created",
                    draft_id=draft_id,
                    lines=len(parse_result.lines),
                    user_id=telegram_user_id,
                    chat_id=chat_id,
                )

        return PreviewResult(draft_id=draft_id, preview_text=preview, hard_error="")

    async def confirm(self, *, draft_id: str, telegram_user_id: int) -> ConfirmResult:
        async with self.session_factory() as session:
            async with session.begin():
                claimed = await self.materials_repo.claim_for_sending(session, draft_id=draft_id, telegram_user_id=telegram_user_id)
                if not claimed:
                    req = await self.materials_repo.get_by_draft_id(session, draft_id)
                    if req is None:
                        return ConfirmResult(False, "Черновик не найден.")
                    if req.telegram_user_id != telegram_user_id:
                        return ConfirmResult(False, "Нет доступа к этой заявке.")
                    if req.status == "failed":
                        return ConfirmResult(False, "❌ Предыдущая попытка отправки завершилась ошибкой.\n\nСоздайте новую заявку командой /materials.")
                    return ConfirmResult(False, "Уже обработано.")

                req = await self.materials_repo.get_by_draft_id(session, draft_id)
                scope_id = req.chat_id or telegram_user_id  # type: ignore[union-attr]

                cooldown_minutes = await self.settings_service.get_cooldown_minutes(session)
                if cooldown_minutes > 0:
                    rl_row = await self.rate_limits_repo.get(session, scope_type=_MAT_SCOPE, scope_id=scope_id)
                    if rl_row is not None:
                        _now = datetime.now(timezone.utc)
                        _last = rl_row.last_request_at
                        if _last.tzinfo is None:
                            _last = _last.replace(tzinfo=timezone.utc)
                        else:
                            _last = _last.astimezone(timezone.utc)
                        _next = _last + timedelta(minutes=cooldown_minutes)
                        if _now < _next:
                            remaining = int((_next - _now).total_seconds())
                            await self.materials_repo.update_status(session, draft_id=draft_id, status="draft")
                            _m, _s = divmod(remaining, 60)
                            until_local = _next.astimezone().strftime("%H:%M")
                            return ConfirmResult(
                                False,
                                "⏱ Заявку пока нельзя отправить: cooldown активен.\n\n"
                                f"Следующая отправка возможна через {_m} мин. {_s} сек. (до {until_local}).\n"
                                "Нажмите «✅ Подтвердить» после окончания ожидания.",
                                keep_keyboard=True,
                            )

                counter = await self.materials_repo.increment_daily_counter(session, chat_id=scope_id, counter_date=req.request_date)  # type: ignore[union-attr]
                request_number = f"{req.request_date.strftime('%y%m%d')}-{req.ps_number or '???'}-{counter}"  # type: ignore[union-attr]
                await self.materials_repo.assign_number(session, draft_id=draft_id, counter=counter, request_number=request_number)

                recipient_email = req.recipient_email or await self.settings_service.get_recipient_email(session)  # type: ignore[union-attr]

                obj_data: dict = {}  # type: ignore[type-arg]
                if req.object_id:  # type: ignore[union-attr]
                    obj = await self.objects_repo.get_by_id(session, req.object_id)  # type: ignore[union-attr]
                    if obj:
                        obj_data = _build_obj_data(obj)

                draft = MaterialDraft(
                    draft_id=draft_id,
                    chat_id=req.chat_id or telegram_user_id,  # type: ignore[union-attr]
                    telegram_user_id=telegram_user_id,
                    object_id=req.object_id,  # type: ignore[union-attr]
                    ps_number=req.ps_number,  # type: ignore[union-attr]
                    request_date=req.request_date,  # type: ignore[union-attr]
                    counter=counter,
                    request_number=request_number,
                    recipient_email=recipient_email,
                    user_full_name=req.user_full_name or "",  # type: ignore[union-attr]
                    lines=[
                        MaterialLine(
                            line_no=item.line_no,
                            name=item.name,
                            type_mark=item.type_mark or "",
                            qty=item.qty,
                            unit=item.unit,
                        )
                        for item in sorted(req.items, key=lambda i: i.line_no)  # type: ignore[union-attr]
                    ],
                )

        try:
            excel_bytes: bytes = await asyncio.to_thread(fill_excel_template, draft, obj_data)
        except Exception as exc:
            logger.error("excel_generation_failed", draft_id=draft_id, error=str(exc))
            async with self.session_factory() as session:
                async with session.begin():
                    await self.materials_repo.update_status(session, draft_id=draft_id, status="failed", error_code="EXCEL_ERROR", error_message=str(exc)[:512])
            return ConfirmResult(False, "❌ Не удалось сформировать файл заявки.\n\nОбратитесь к инженеру ПТО.")

        ps = draft.ps_number or "объект"
        today_str = draft.request_date.strftime("%d.%m.%Y")
        filename = build_file_name(draft)
        subject = f"ПС {ps}: Заявка от {today_str} ({draft.counter})"
        body = (
            "Заявка на материалы\n\n"
            f"Объект/ПС: {ps}\n"
            f"Дата: {today_str}\n"
            f"Номер: {draft.request_number}\n"
            f"Заявку сформировал: {draft.user_full_name or '—'}\n"
        )

        try:
            await self.email_dispatcher.send_with_attachment(
                to_email=recipient_email,
                subject=subject,
                body=body,
                attachment_bytes=excel_bytes,
                attachment_filename=filename,
            )
        except Exception as exc:
            logger.error("materials_email_failed", draft_id=draft_id, error=str(exc))
            async with self.session_factory() as session:
                async with session.begin():
                    await self.materials_repo.update_status(session, draft_id=draft_id, status="failed", error_code="SMTP_ERROR", error_message=str(exc)[:512])
            return ConfirmResult(False, f"❌ Не удалось отправить заявку на e-mail.\n\nПричина: {type(exc).__name__}\n\nСоздайте новую заявку командой /materials.")

        now = datetime.now(timezone.utc)
        next_time = now + timedelta(minutes=cooldown_minutes)

        async with self.session_factory() as session:
            async with session.begin():
                await self.materials_repo.update_status(session, draft_id=draft_id, status="sent")
                if cooldown_minutes > 0:
                    await self.rate_limits_repo.upsert(session, scope_type=_MAT_SCOPE, scope_id=scope_id, last_request_at=now)

        object_display = obj_data.get("ps_name") or ps
        tail = ""
        if cooldown_minutes > 0:
            tail = (
                f"\n\n⏱ Следующую заявку можно отправить через {cooldown_minutes} мин.\n"
                f"Не ранее: {next_time.astimezone().strftime('%d.%m.%Y %H:%M')}"
            )

        return ConfirmResult(
            True,
            "✅ Заявка на материалы отправлена на проверку.\n\n"
            f"Объект: {object_display}\n"
            f"ПС: {ps}\n"
            f"Дата: {today_str} ({draft.counter})\n"
            f"E-mail получателя: {recipient_email}"
            + tail,
        )

    async def cancel(self, *, draft_id: str, telegram_user_id: int) -> str:
        async with self.session_factory() as session:
            async with session.begin():
                req = await self.materials_repo.get_by_draft_id(session, draft_id)
                if req is None:
                    return "Черновик не найден."
                if req.status in ("sent", "cancelled", "sending"):
                    return "Уже обработано."
                if req.telegram_user_id != telegram_user_id:
                    return "Нет доступа к этой заявке."
                await self.materials_repo.update_status(session, draft_id=draft_id, status="cancelled")
        logger.info("materials_cancelled", draft_id=draft_id, user=telegram_user_id)
        return "❌ Заявка отменена. Ничего не отправлено."
