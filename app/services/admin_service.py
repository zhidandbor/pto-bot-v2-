from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings
from app.db.repositories.admins import AdminRepository
from app.db.repositories.groups import GroupsRepository
from app.db.repositories.objects import ObjectsRepository
from app.db.repositories.users import UsersRepository
from app.services.audit_service import AuditService
from app.services.settings_service import SettingsService


@dataclass(frozen=True)
class AdminService:
    """Facade for admin operations.

    Business logic for object/group/user management lives in the individual
    repositories and SettingsService.  This service is the DI-registered
    orchestration point for operations that span multiple repositories or
    require audit logging.  Admin router handlers currently access repositories
    directly; future refactors can delegate through this service.
    """

    settings: Settings
    users_repo: UsersRepository
    admins_repo: AdminRepository
    groups_repo: GroupsRepository
    objects_repo: ObjectsRepository
    settings_service: SettingsService
    audit: AuditService
