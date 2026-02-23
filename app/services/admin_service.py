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
    """Сервис административных операций.

    Инжектируется через Container и предоставляет единую точку входа
    для операций управления объектами, группами и пользователями.
    Текущие реализации находятся непосредственно в роутерах (admin.py,
    superadmin.py); этот класс является точкой консолидации на будущее.
    """

    settings: Settings
    users_repo: UsersRepository
    admins_repo: AdminRepository
    groups_repo: GroupsRepository
    objects_repo: ObjectsRepository
    settings_service: SettingsService
    audit: AuditService
