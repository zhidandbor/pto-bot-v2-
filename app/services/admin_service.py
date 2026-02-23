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
    """Service layer for admin operations.

    Holds references to all repositories and services required for
    administrative commands.  Business logic is currently implemented
    directly in the Telegram router handlers (telegram/routers/admin.py
    and superadmin.py); this class exists as the designated DI slot for
    future extraction of that logic into the service layer.
    """

    settings: Settings
    users_repo: UsersRepository
    admins_repo: AdminRepository
    groups_repo: GroupsRepository
    objects_repo: ObjectsRepository
    settings_service: SettingsService
    audit: AuditService
