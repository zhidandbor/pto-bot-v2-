from __future__ import annotations

from dataclasses import dataclass

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class HelpService:
    registry: object
    rbac: object
    settings_service: object

    def __post_init__(self) -> None:
        logger.info("help_service_init_done")