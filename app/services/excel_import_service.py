from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class ExcelImportService:
    settings: Settings
    reader: object
    objects_repo: object
    excel_imports_repo: object
    audit: object

    def __post_init__(self) -> None:
        logger.info("excel_import_service_init_done")
