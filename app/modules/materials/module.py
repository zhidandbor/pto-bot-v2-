from __future__ import annotations

from typing import Iterable

from aiogram import Router

from app.core.module_registry import BotModule, CommandSpec
from app.db.repositories.materials import MaterialsRepository
from app.db.repositories.objects import ObjectsRepository
from app.db.repositories.rate_limits import RateLimitsRepository
from app.modules.materials.email_dispatcher import MaterialsEmailDispatcher
from app.modules.materials.handlers import build_router
from app.modules.materials.service import MaterialsService


class MaterialsModule:
    def __init__(self, router: Router, cmds: list[CommandSpec]) -> None:
        self.name = "materials"
        self._router = router
        self._cmds = cmds

    def routers(self) -> Iterable[Router]:
        return [self._router]

    def commands(self) -> Iterable[CommandSpec]:
        return self._cmds

    def help_sections(self) -> list[str]:
        return [
            "📦 <b>Заявки на материалы</b>\n"
            "Команда: /materials\n"
            "Формат строки: Имя, Тип, Количество Единицы\n"
            "Пример: уголок г/к, 50х50х5 L=6 м, 0,156 т\n"
            "Единицы: м, п.м, м², м³, кг, т, шт., компл., уп., рул., л\n"
            "В личном чате первая строка — объект (напр. ПС 55)."
        ]


def create_module(container: object) -> BotModule:  # type: ignore[type-arg]
    email_dispatcher = MaterialsEmailDispatcher(
        settings=container.settings  # type: ignore[attr-defined]
    )
    service = MaterialsService(
        session_factory=container.session_factory,  # type: ignore[attr-defined]
        materials_repo=MaterialsRepository(),
        objects_repo=ObjectsRepository(),
        rate_limits_repo=RateLimitsRepository(),
        settings_service=container.settings_service,  # type: ignore[attr-defined]
        email_dispatcher=email_dispatcher,
    )
    router = build_router(service)
    cmds = [
        CommandSpec(
            command="materials",
            description="Заявка на материалы",
            required_role="user",
            requires_object_context=False,
            rate_limited=True,
        )
    ]
    module = MaterialsModule(router=router, cmds=cmds)
    container.registry.register_module(module)  # type: ignore[attr-defined]
    return module
