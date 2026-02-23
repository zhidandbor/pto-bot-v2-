from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ExcelImport


class ExcelImportsRepository:

    async def create(
        self,
        session: AsyncSession,
        *,
        file_name: str,
        imported_by: int,
        status: str = "running",
    ) -> ExcelImport:
        row = ExcelImport(
            file_name=file_name,
            imported_by=imported_by,
            status=status,
            stats_json={},
            errors_json={},
        )
        session.add(row)
        await session.flush()
        return row

    async def finish(
        self,
        session: AsyncSession,
        *,
        import_id: int,
        status: str,
        stats: dict[str, Any],
        errors: dict[str, Any],
    ) -> None:
        res = await session.execute(
            select(ExcelImport).where(ExcelImport.id == import_id)
        )
        row = res.scalar_one_or_none()
        if row is None:
            return
        row.status = status
        row.stats_json = stats
        row.errors_json = errors
        row.finished_at = datetime.now(timezone.utc)
        session.add(row)
        await session.flush()

    async def get_by_id(
        self, session: AsyncSession, import_id: int
    ) -> ExcelImport | None:
        res = await session.execute(
            select(ExcelImport).where(ExcelImport.id == import_id)
        )
        return res.scalar_one_or_none()

    async def list_recent(
        self, session: AsyncSession, limit: int = 20
    ) -> list[ExcelImport]:
        res = await session.execute(
            select(ExcelImport)
            .order_by(ExcelImport.started_at.desc())
            .limit(limit)
        )
        return list(res.scalars().all())
