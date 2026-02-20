from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.repositories.settings import SettingsRepository


@dataclass(frozen=True)
class SettingsService:
    settings: Settings
    repo: SettingsRepository

    async def ensure_defaults(self) -> None:
        # called with explicit session by middleware lifecycle (startup uses a dedicated session)
        # This method is invoked via Container.startup() with a temporary session.
        from sqlalchemy.ext.asyncio import AsyncSession
        from app.core.container import build_container  # avoid import cycle in typing-time

        # no-op placeholder, actual initialization performed in initialize_defaults(session)
        return

    async def initialize_defaults(self, session: AsyncSession) -> None:
        cur_recipient = await self.repo.get(session, "recipient_email")
        if not cur_recipient and self.settings.default_recipient_email:
            await self.repo.set(session, "recipient_email", self.settings.default_recipient_email)

        cur_cd = await self.repo.get(session, "cooldown_minutes")
        if not cur_cd:
            await self.repo.set(session, "cooldown_minutes", str(self.settings.default_cooldown_minutes))

    async def get_recipient_email(self, session: AsyncSession) -> str:
        v = await self.repo.get(session, "recipient_email")
        return v or self.settings.default_recipient_email

    async def set_recipient_email(self, session: AsyncSession, email: str) -> None:
        await self.repo.set(session, "recipient_email", email)

    async def get_cooldown_minutes(self, session: AsyncSession) -> int:
        v = await self.repo.get(session, "cooldown_minutes")
        if not v:
            return int(self.settings.default_cooldown_minutes)
        try:
            return max(0, int(v))
        except ValueError:
            return int(self.settings.default_cooldown_minutes)

    async def set_cooldown_minutes(self, session: AsyncSession, minutes: int) -> None:
        await self.repo.set(session, "cooldown_minutes", str(max(0, int(minutes))))
