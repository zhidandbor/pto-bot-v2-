from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from aiogram import Router

from app.core.module_registry import BotModule, CommandSpec


@dataclass(frozen=True)
class MaterialsModule:
    name: str = "materials"

    def routers(self) -> Iterable[Router]:
        return []

    def commands(self) -> Iterable[CommandSpec]:
        return []

    def help_sections(self) -> list[str]:
        return [
            "Материалы: модуль подключён (утилиты/формирование Excel), сценарии в разработке."
        ]


def create_module(container: object) -> MaterialsModule:
    return MaterialsModule()
