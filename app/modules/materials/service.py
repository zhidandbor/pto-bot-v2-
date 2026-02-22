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

# Отдельный scope чтобы не конфликтовать с общим ядровым rate_limit
_MAT_SCOPE = "mat_chat"


def _new_draft_id() -> str:
    return secrets.token_hex(6)  # 12 hex-символов


class PreviewResult(NamedTuple):
    draft_id: str
    preview_text: str
    hard_error: str  # непустая → показать ошибку вместо preview


class ConfirmResult(NamedTuple):
    ok: bool
    message: str


def _build_obj_data(obj: object) -> dict:  # type: ignore[type-arg]
    """Маппинг полей Object → dict для fill_excel_template."""
    work_period = ""
    if getattr(obj, "work_start", None):
        start = obj.work_start.strftime("%d.%m.%Y")  # type: ignore[union-attr]
        end = obj.work_end.strftime("%d.%m.%Y") if getattr(obj, "work_end", None) else ""  # type: ignore[union-attr]
        work_period = f"{start} — {end}" if end else start

    extra: dict = getattr(obj, "extra", {}) or {}
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

    # ------------------------------------------------------------------
    # Cooldown: read-only, без обновления (обновление — только в confirm)
    # ------------------------------------------------------------------

    async def check_cooldown(self, *, scope_id: int) -> tuple[bool, int]:
        """(allowed, remaining_seconds). НЕ обновляет last_request_at."""
        async with self.session_factory() as session:
            cooldown_minutes = await self.settings_service.get_cooldown_minutes(session)
            if cooldown_minutes <= 0:
                return True, 0
            row = await self.rate_limits_repo.get(
                session, scope_type=_MAT_SCOPE, scope_id=scope_id
            )
            if not row:
                return True, 0
            now = datetime.now(timezone.utc)
            next_allowed = row.last_request_at.replace(tzinfo=timezone.utc) + timedelta(
                minutes=cooldown_minutes
            )
            if now < next_allowed:
                return False, int((next_allowed - now).total_seconds())
            return True, 0

    # ------------------------------------------------------------------
    # Шаг 1: Парсинг → объект → счётчик → черновик → текст предпросмотра
    # ------------------------------------------------------------------

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

                # --- Определение объекта ---
                if is_private:
                    raw = [ln.strip() for ln in text.splitlines() if ln.strip()]
                    if not raw:
                        return PreviewResult("", "", "Сообщение пустое.")
                    found = await self.objects_repo.search(session, raw[0], limit=1)
                    if not found:
                        return PreviewResult(
                            "", "",
                            "⚠️ В личном чате нужно указать объект первой строкой.\n\n"
                            "Пример:\nПС 55\nуголок г/к (50х50х5, L=6 м) - 0,156 т",
                        )
                    obj = found[0]
                    lines_text = "\n".join(raw[1:])
                else:
                    linked = await self.objects_repo.list_linked_objects(session, chat_id)
                    if linked:
                        obj = linked[0]

                # --- Парсинг ---
                parse_result = parse_materials_message(lines_text)
                if not parse_result.lines:
                    err_detail = "\n".join(
                        f"  • {e}" for e in parse_result.errors[:5]
                    )
                    return PreviewResult(
                        "", "",
                        "⚠️ Не удалось распознать позиции заявки.\n\n"
                        "Проверьте формат строк:\n[Имя] ([Тип]) - [Количество] [Единицы]\n\n"
                        "Пример:\nуголок г/к (50х50х5, L=6 м) - 0,156 т"
                        + (f"\n\nОшибки:\n{err_detail}" if err_detail else ""),
                    )

                # --- Настройки ---
                recipient_email = await self.settings_service.get_recipient_email(session)

                # --- Атомарный счётчик (FR-MAT-09.3: в каждой группе свой) ---
                today = date.today()
                counter_scope = chat_id if not is_private else telegram_user_id
                counter = await self.materials_repo.increment_daily_counter(
                    session, chat_id=counter_scope, counter_date=today
                )

                ps_number = (
                    getattr(obj, "ps_number", None)
                    or getattr(obj, "ps_name", None)
                    or "???"
                ) if obj else "???"
                request_number = f"{today.strftime('%y%m%d')}-{ps_number}-{counter}"
                draft_id = _new_draft_id()

                # --- Сохранение черновика ---
                await self.materials_repo.create_request(
                    session,
                    draft_id=draft_id,
                    chat_id=chat_id if not is_private else None,
                    telegram_user_id=telegram_user_id,
                    object_id=getattr(obj, "id", None) if obj else None,
                    ps_number=ps_number,
                    request_date=today,
                    counter=counter,
                    request_number=request_number,
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
                    f"📦 Заявка на материалы — ПРЕДПРОСМОТР\n\n"
                    f"Объект: {object_name}\n"
                    f"ПС: {ps_number}\n"
                    f"Дата: {today.strftime('%d.%m.%Y')} ({counter})\n\n"
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

    # ------------------------------------------------------------------
    # Шаг 2: confirm → Excel (asyncio.to_thread) → email → статус → cooldown
    # ------------------------------------------------------------------

    async def confirm(
        self,
        *,
        draft_id: str,
        telegram_user_id: int,
    ) -> ConfirmResult:
        # --- Читаем черновик (отдельная сессия, read-only) ---
        async with self.session_factory() as session:
            req = await self.materials_repo.get_by_draft_id(session, draft_id)
            if req is None:
                return ConfirmResult(False, "Черновик не найден.")

            # Идемпотентность: повторное нажатие не создаёт повторных отправок
            if req.status in ("sent", "cancelled"):
                return ConfirmResult(False, "Уже обработано.")

            if req.telegram_user_id != telegram_user_id:
                return ConfirmResult(False, "Нет доступа к этой заявке.")

            recipient_email = (
                req.recipient_email
                or await self.settings_service.get_recipient_email(session)
            )
            cooldown_minutes = await self.settings_service.get_cooldown_minutes(session)

            # Данные объекта для шапки Excel (пока сессия открыта)
            obj_data: dict = {}  # type: ignore[type-arg]
            if req.object_id:
                obj = await self.objects_repo.get_by_id(session, req.object_id)
                if obj:
                    obj_data = _build_obj_data(obj)

            # Собираем MaterialDraft пока items доступны через relationship
            draft = MaterialDraft(
                draft_id=draft_id,
                chat_id=req.chat_id or telegram_user_id,
                telegram_user_id=telegram_user_id,
                object_id=req.object_id,
                ps_number=req.ps_number,
                request_date=req.request_date,
                counter=req.counter,
                request_number=req.request_number or "",
                recipient_email=recipient_email,
                user_full_name=req.user_full_name or "",
                lines=[
                    MaterialLine(
                        line_no=item.line_no,
                        name=item.name,
                        type_mark=item.type_mark or "",
                        qty=item.qty,
                        unit=item.unit,
                    )
                    for item in sorted(req.items, key=lambda i: i.line_no)
                ],
            )
            scope_id = req.chat_id or telegram_user_id

        # --- Excel в отдельном потоке (NFR: не блокировать event loop) ---
        try:
            excel_bytes: bytes = await asyncio.to_thread(
                fill_excel_template, draft, obj_data
            )
        except Exception as exc:
            logger.error("excel_generation_failed", draft_id=draft_id, error=str(exc))
            async with self.session_factory() as session:
                async with session.begin():
                    await self.materials_repo.update_status(
                        session,
                        draft_id=draft_id,
                        status="failed",
                        error_code="EXCEL_ERROR",
                        error_message=str(exc)[:512],
                    )
            return ConfirmResult(
                False,
                "❌ Не удалось сформировать файл заявки.\n\nОбратитесь к инженеру ПТО.",
            )

        # --- Имя файла и тема письма (FR-MAT-16, FR-MAT-17) ---
        ps = draft.ps_number or "объект"
        today_str = draft.request_date.strftime("%d.%m.%Y")
        filename = build_file_name(draft)
        subject = f"ПС {ps}: Заявка от {today_str} ({draft.counter})"
        body = (
            f"Заявка на материалы\n\n"
            f"Объект/ПС: {ps}\n"
            f"Дата: {today_str}\n"
            f"Номер: {draft.request_number}\n"
            f"Заявку сформировал: {draft.user_full_name or '—'}\n"
        )

        # --- Отправка email ---
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
                    await self.materials_repo.update_status(
                        session,
                        draft_id=draft_id,
                        status="failed",
                        error_code="SMTP_ERROR",
                        error_message=str(exc)[:512],
                    )
            return ConfirmResult(
                False,
                f"❌ Не удалось отправить заявку на e-mail.\n\n"
                f"Причина: {type(exc).__name__}\n\n"
                "Попробуйте ещё раз позже или обратитесь к инженеру ПТО.",
            )

        # --- Успех: статус + cooldown ТОЛЬКО после успешной отправки (FR-MAT-10) ---
        now = datetime.now(timezone.utc)
        next_time = now + timedelta(minutes=cooldown_minutes)

        async with self.session_factory() as session:
            async with session.begin():
                await self.materials_repo.update_status(
                    session, draft_id=draft_id, status="sent"
                )
                await self.rate_limits_repo.upsert(
                    session,
                    scope_type=_MAT_SCOPE,
                    scope_id=scope_id,
                    last_request_at=now,
                )

        logger.info(
            "materials_sent",
            draft_id=draft_id,
            to=recipient_email,
            ps=ps,
            counter=draft.counter,
        )

        object_display = obj_data.get("ps_name") or ps
        return ConfirmResult(
            True,
            f"✅ Заявка на материалы отправлена на проверку.\n\n"
            f"Объект: {object_display}\n"
            f"ПС: {ps}\n"
            f"Дата: {today_str} ({draft.counter})\n"
            f"E-mail получателя: {recipient_email}\n\n"
            f"⏱ Следующую заявку на материалы можно отправить через {cooldown_minutes} мин.\n"
            f"Не ранее: {next_time.astimezone().strftime('%d.%m.%Y %H:%M')}",
        )

    # ------------------------------------------------------------------
    # Отмена: НЕ запускает cooldown (FR-MAT-10)
    # ------------------------------------------------------------------

    async def cancel(self, *, draft_id: str, telegram_user_id: int) -> str:
        async with self.session_factory() as session:
            async with session.begin():
                req = await self.materials_repo.get_by_draft_id(session, draft_id)
                if req is None:
                    return "Черновик не найден."
                if req.status in ("sent", "cancelled"):
                    return "Уже обработано."
                if req.telegram_user_id != telegram_user_id:
                    return "Нет доступа к этой заявке."
                await self.materials_repo.update_status(
                    session, draft_id=draft_id, status="cancelled"
                )
        logger.info("materials_cancelled", draft_id=draft_id, user=telegram_user_id)
        return "❌ Заявка отменена. Ничего не отправлено."
