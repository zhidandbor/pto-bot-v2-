from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.repositories.admins import AdminRepository
from app.db.repositories.users import UsersRepository


@dataclass(frozen=True)
class RBACService:
    settings: Settings
    admins_repo: AdminRepository
    users_repo: UsersRepository

    def is_superadmin(self, telegram_user_id: int) -> bool:
        return int(telegram_user_id) == int(self.settings.superadmin_id)

    async def is_admin(self, session: AsyncSession, telegram_user_id: int) -> bool:
        return await self.admins_repo.is_admin(session, telegram_user_id)

    async def is_allowed_private(self, session: AsyncSession, telegram_user_id: int) -> bool:
        return await self.users_repo.is_allowed_private(session, telegram_user_id)
