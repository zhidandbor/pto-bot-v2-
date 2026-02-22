from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.db.models import MaterialGroupDailyCounter, MaterialItem, MaterialRequest

logger = get_logger(__name__)


class MaterialsRepository:
    async def create_request(
        self,
        session: AsyncSession,
        *,
        draft_id: str,
        chat_id: int | None,
        telegram_user_id: int,
        object_id: int | None,
        ps_number: str | None,
        request_date: date,
        counter: int,
        request_number: str | None,
        recipient_email: str | None,
        user_full_name: str | None,
        lines: list[dict],
    ) -> MaterialRequest:
        request = MaterialRequest(
            draft_id=draft_id,
            chat_id=chat_id,
            telegram_user_id=telegram_user_id,
            object_id=object_id,
            ps_number=ps_number,
            request_date=request_date,
            counter=counter,
            request_number=request_number,
            recipient_email=recipient_email,
            user_full_name=user_full_name,
            status="draft",
        )
        session.add(request)
        await session.flush()

        for line in lines:
            session.add(
                MaterialItem(
                    request_id=request.id,
                    line_no=line["line_no"],
                    name=line["name"],
                    type_mark=line.get("type_mark") or None,
                    qty=Decimal(str(line["qty"])),
                    unit=line["unit"],
                )
            )

        await session.flush()
        logger.debug("materials_request_created", draft_id=draft_id, lines=len(lines))
        return request

    async def get_by_draft_id(
        self, session: AsyncSession, draft_id: str
    ) -> MaterialRequest | None:
        result = await session.execute(
            select(MaterialRequest)
            .options(selectinload(MaterialRequest.items))
            .where(MaterialRequest.draft_id == draft_id)
        )
        return result.scalar_one_or_none()

    async def update_status(
        self,
        session: AsyncSession,
        *,
        draft_id: str,
        status: str,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        await session.execute(
            update(MaterialRequest)
            .where(MaterialRequest.draft_id == draft_id)
            .values(
                status=status,
                error_code=error_code,
                error_message=error_message,
                updated_at=datetime.now(timezone.utc),
            )
        )

    async def claim_for_sending(
        self,
        session: AsyncSession,
        *,
        draft_id: str,
        telegram_user_id: int,
    ) -> bool:
        """
        Атомарный переход статуса draft → sending.

        Возвращает True, если доступ получен (1 строка обновлена).
        False — заявка уже обрабатывается / отменена / чужая / не найдена.
        Используется внутри активной session.begin() транзакции.
        """
        result = await session.execute(
            update(MaterialRequest)
            .where(
                MaterialRequest.draft_id == draft_id,
                MaterialRequest.telegram_user_id == telegram_user_id,
                MaterialRequest.status == "draft",
            )
            .values(status="sending", updated_at=datetime.now(timezone.utc))
            .returning(MaterialRequest.id)
        )
        return result.scalar_one_or_none() is not None

    async def assign_number(
        self,
        session: AsyncSession,
        *,
        draft_id: str,
        counter: int,
        request_number: str,
    ) -> None:
        """
        Записывает порядковый номер и счётчик после успешного increment_daily_counter.
        Вызывать только внутри транзакции claim_for_sending.
        """
        await session.execute(
            update(MaterialRequest)
            .where(MaterialRequest.draft_id == draft_id)
            .values(
                counter=counter,
                request_number=request_number,
                updated_at=datetime.now(timezone.utc),
            )
        )

    async def increment_daily_counter(
        self, session: AsyncSession, *, chat_id: int, counter_date: date
    ) -> int:
        """UPSERT daily counter, returns new value (1-based)."""
        stmt = (
            pg_insert(MaterialGroupDailyCounter)
            .values(counter_date=counter_date, chat_id=chat_id, last_counter=1)
            .on_conflict_do_update(
                constraint="uq_mat_group_daily_counter",
                set_={
                    "last_counter": MaterialGroupDailyCounter.last_counter + 1
                },
            )
            .returning(MaterialGroupDailyCounter.last_counter)
        )
        result = await session.execute(stmt)
        return result.scalar_one()
