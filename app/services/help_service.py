from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.module_registry import ModuleRegistry
from app.services.rbac import RBACService
from app.services.settings_service import SettingsService


@dataclass(frozen=True, slots=True)
class HelpService:
    registry: ModuleRegistry
    rbac: RBACService
    settings_service: SettingsService

    async def get_start_text(self, session: AsyncSession, role: str) -> str:
        if role == "blocked":
            return "⛔ Нет доступа. Попросите администратора добавить вас (для личных сообщений)."

        recipient = await self.settings_service.get_recipient_email(session)
        cooldown = await self.settings_service.get_cooldown_minutes(session)

        return (
            "PTO-bot запущен.\n"
            "Главное меню: /start, /help, /materials\n\n"
            f"Роль: {role}\n"
            f"Email получателя по умолчанию: {recipient or 'не задан'}\n"
            f"Cooldown: {cooldown} мин."
        )

    async def get_help_text(self, session: AsyncSession, role: str) -> str:
        if role == "blocked":
            return "⛔ Нет доступа. Попросите администратора добавить вас (для личных сообщений)."

        lines: list[str] = [
            "📖 Справка PTO-bot",
            "",
            "• /materials — создать заявку на материалы (далее следуйте подсказкам бота).",
            "• В личном чате доступ требует разрешения администратора.",
        ]

        if role in ("admin", "superadmin"):
            lines.append("• /commands — список админских команд.")

        # Доп. секции справки от модулей
        for section in self.registry.help_sections():
            s = (section or "").strip()
            if s:
                lines.append("")
                lines.append(s)

        return "\n".join(lines)
