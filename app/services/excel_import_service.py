from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import NamedTuple

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.logging import get_logger
from app.db.repositories.excel_imports import ExcelImportsRepository
from app.db.repositories.groups import GroupsRepository
from app.db.repositories.objects import ObjectsRepository
from app.services.audit_service import AuditService
from app.services.objects_excel_reader import ObjectRow, ObjectsExcelReader

logger = get_logger(__name__)


class ImportResult(NamedTuple):
    ok: bool
    created: int
    updated: int
    groups_linked: int
    row_errors: list[str]
    fatal_error: str


@dataclass
class ExcelImportService:
    """Оркестрирует импорт объектов из data_objects.xlsx в БД.

    Шаги:
    1. Чтение файла в отдельном потоке (не блокирует event loop).
    2. Запись лога запуска импорта (ExcelImport.status=running).
    3. Для каждой строки: upsert Object + upsert Group + link ObjectGroupLink.
    4. Завершение лога (done / done_with_errors / failed) + AuditLog.
    """

    session_factory: async_sessionmaker  # type: ignore[type-arg]
    reader: ObjectsExcelReader
    objects_repo: ObjectsRepository
    groups_repo: GroupsRepository
    excel_imports_repo: ExcelImportsRepository
    audit: AuditService

    async def import_from_bytes(
        self,
        *,
        file_bytes: bytes,
        filename: str,
        imported_by: int,
    ) -> ImportResult:
        # --- Шаг 1: читаем файл в отдельном потоке ---
        try:
            read_result = await asyncio.to_thread(
                self.reader.read, file_bytes, filename=filename
            )
        except Exception as exc:
            logger.error("excel_import_read_failed", filename=filename, error=str(exc))
            return ImportResult(
                ok=False,
                created=0, updated=0, groups_linked=0,
                row_errors=[],
                fatal_error=f"Ошибка чтения файла: {exc}",
            )

        if not read_result.rows:
            return ImportResult(
                ok=False,
                created=0, updated=0, groups_linked=0,
                row_errors=read_result.errors,
                fatal_error="Файл не содержит корректных строк объектов.",
            )

        # --- Шаг 2: фиксируем запуск импорта ---
        async with self.session_factory() as session:
            async with session.begin():
                import_log = await self.excel_imports_repo.create(
                    session,
                    file_name=filename,
                    imported_by=imported_by,
                )
                import_id: int = import_log.id

        created = 0
        updated = 0
        groups_linked = 0
        row_errors: list[str] = list(read_result.errors)

        # --- Шаг 3: upsert объектов + привязка групп ---
        for row in read_result.rows:
            try:
                async with self.session_factory() as session:
                    async with session.begin():
                        obj, was_created = await self.objects_repo.upsert_by_dedup_key(
                            session,
                            dedup_key=row.dedup_key,
                            fields=_build_object_fields(row),
                        )
                        if was_created:
                            created += 1
                        else:
                            updated += 1

                        if row.chat_id is not None:
                            await self.groups_repo.ensure_group(
                                session,
                                chat_id=row.chat_id,
                                title=_build_group_title(row),
                                added_by=None,
                            )
                            await self.objects_repo.link_group(
                                session,
                                object_id=obj.id,
                                chat_id=row.chat_id,
                            )
                            groups_linked += 1

            except Exception as exc:
                msg = f"Строка {row.row_num} [{row.dedup_key}]: {exc}"
                row_errors.append(msg)
                logger.error(
                    "excel_row_import_failed",
                    row=row.row_num,
                    dedup_key=row.dedup_key,
                    error=str(exc),
                )

        # --- Шаг 4: финализируем лог ---
        if row_errors and (created + updated) == 0:
            final_status = "failed"
        elif row_errors:
            final_status = "done_with_errors"
        else:
            final_status = "done"

        async with self.session_factory() as session:
            async with session.begin():
                await self.excel_imports_repo.finish(
                    session,
                    import_id=import_id,
                    status=final_status,
                    stats={
                        "created": created,
                        "updated": updated,
                        "groups_linked": groups_linked,
                        "total_rows": len(read_result.rows),
                    },
                    errors={"rows": row_errors[:50]},
                )
                await self.audit.log(
                    session,
                    actor_user_id=imported_by,
                    action="excel_import",
                    entity_type="objects",
                    entity_id=str(import_id),
                    payload={
                        "file": filename,
                        "created": created,
                        "updated": updated,
                        "groups_linked": groups_linked,
                        "row_errors": len(row_errors),
                        "status": final_status,
                    },
                )

        logger.info(
            "excel_import_finished",
            import_id=import_id,
            filename=filename,
            status=final_status,
            created=created,
            updated=updated,
            groups_linked=groups_linked,
            row_errors=len(row_errors),
        )

        return ImportResult(
            ok=final_status != "failed",
            created=created,
            updated=updated,
            groups_linked=groups_linked,
            row_errors=row_errors,
            fatal_error="",
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_object_fields(row: ObjectRow) -> dict:  # type: ignore[type-arg]
    """Строит словарь полей для ObjectsRepository.upsert_by_dedup_key()."""
    extra: dict = {}  # type: ignore[type-arg]
    _set_if(extra, "customer_position_1", row.customer_position_1)
    _set_if(extra, "customer_fio_1", row.customer_fio_1)
    _set_if(extra, "customer_name_patronymic_1", row.customer_name_patronymic_1)
    _set_if(extra, "customer_position_2", row.customer_position_2)
    _set_if(extra, "customer_fio_2", row.customer_fio_2)
    _set_if(extra, "customer_name_patronymic_2", row.customer_name_patronymic_2)
    _set_if(extra, "contractor", row.contractor)
    _set_if(extra, "contractor_oks_name", row.contractor_oks_name)
    _set_if(extra, "contractor_oks_tel", row.contractor_oks_tel)
    _set_if(extra, "contractor_osovn_name", row.contractor_osovn_name)
    _set_if(extra, "contractor_osovn_tel", row.contractor_osovn_tel)

    return {
        "ps_number": row.ps_number,
        "ps_name": row.ps_name,
        "work_type": row.work_type,
        "title_name": row.title_name,
        "address": row.address,
        "contract_number": row.contract_number,
        "contract_start": row.contract_start,
        "contract_end": row.contract_end,
        "request_number": row.request_number,
        "work_start": row.work_start,
        "work_end": row.work_end,
        "customer": row.customer,
        "extra": extra,
    }


def _set_if(d: dict, key: str, val: str | None) -> None:  # type: ignore[type-arg]
    if val:
        d[key] = val


def _build_group_title(row: ObjectRow) -> str:
    parts = [f"ПС {row.ps_number}" if row.ps_number else "ПС ?"]
    if row.ps_name:
        parts.append(row.ps_name)
    if row.work_type:
        parts.append(row.work_type)
    return " — ".join(parts)
