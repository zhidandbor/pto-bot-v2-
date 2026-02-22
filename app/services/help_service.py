from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.module_registry import ModuleRegistry
from app.services.rbac import RBACService
from app.services.settings_service import SettingsService


_ROLE_ORDER: dict[str, int] = {"superadmin": 3, "admin": 2, "user": 1, "blocked": 0}


@dataclass(frozen=True, slots=True)
class HelpService:
    registry: ModuleRegistry
    rbac: RBACService
    settings_service: SettingsService

    def _role_allows(self, user_role: str, required_role: str) -> bool:
        return _ROLE_ORDER.get(user_role, 0) >= _ROLE_ORDER.get(required_role, 1)

    async def get_start_text(self, session: AsyncSession, role: str) -> str:
        if role == "blocked":
            return "⛔ Нет доступа. Попросите администратора добавить вас (для личных сообщений)."

        recipient = await self.settings_service.get_recipient_email(session)
        cooldown = await self.settings_service.get_cooldown_minutes(session)

        return (
            "PTO-bot запущен.\n"
            "Команды: /help\n\n"
            f"Роль: {role}\n"
            f"Email получателя по умолчанию: {recipient or 'не задан'}\n"
            f"Cooldown: {cooldown} мин."
        )

    async def get_help_text(self, session: AsyncSession, role: str) -> str:
        if role == "blocked":
            return "⛔ Нет доступа. Попросите администратора добавить вас (для личных сообщений)."

        lines: list[str] = ["📖 Доступные команды:"]
        for spec in self.registry.all_commands():
            if self._role_allows(role, spec.required_role):
                lines.append(f"/{spec.command} — {spec.description}")

        # Доп. секции справки от модулей (если модули их предоставляют)
        for section in self.registry.help_sections():
            if section.strip():
                lines.append("")
                lines.append(section.strip())

        return "\n".join(lines)
