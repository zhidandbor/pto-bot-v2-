from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ExcelImport


class ExcelImportsRepository:
    async def create(self, session: AsyncSession, *, file_name: str, imported_by: int) -> ExcelImport:
        row = ExcelImport(file_name=file_name, imported_by=imported_by, status="running", stats_json={}, errors_json={})
        session.add(row)
        await session.flush()
        return row

    async def finish(
        self,
        session: AsyncSession,
        *,
        import_id: int,
        status: str,
        stats_json: dict[str, Any],
        errors_json: dict[str, Any],
    ) -> None:
        res = await session.execute(select(ExcelImport).where(ExcelImport.id == import_id))
        row = res.scalar_one()
        row.status = status
        row.stats_json = stats_json
        row.errors_json = errors_json
        row.finished_at = datetime.utcnow()
        session.add(row)
        await session.flush()
