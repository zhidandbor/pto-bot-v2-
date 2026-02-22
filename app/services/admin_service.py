from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class AdminService:
    settings: Settings
    users_repo: object
    admins_repo: object
    groups_repo: object
    objects_repo: object
    settings_service: object
    audit: object

    def __post_init__(self) -> None:
        logger.info("admin_service_init_done")