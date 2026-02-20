from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Protocol

from aiogram import Router


@dataclass(frozen=True)
class CommandSpec:
    command: str
    description: str
    required_role: str  # "user" | "admin" | "superadmin"
    requires_object_context: bool
    rate_limited: bool
    rate_limit_exempt: bool = False


class BotModule(Protocol):
    name: str

    def routers(self) -> Iterable[Router]: ...

    def commands(self) -> Iterable[CommandSpec]: ...

    def help_sections(self) -> list[str]: ...


class ModuleRegistry:
    def __init__(self) -> None:
        self._commands: dict[str, CommandSpec] = {}
        self._modules: dict[str, BotModule] = {}

    def register_module(self, module: BotModule) -> None:
        self._modules[module.name] = module
        for spec in module.commands():
            self._commands[spec.command] = spec

    def get_command_spec(self, command: str) -> CommandSpec | None:
        return self._commands.get(command)

    def all_commands(self) -> list[CommandSpec]:
        return sorted(self._commands.values(), key=lambda c: c.command)

    def module_routers(self) -> list[Router]:
        routers: list[Router] = []
        for m in self._modules.values():
            routers.extend(list(m.routers()))
        return routers

    def help_sections(self) -> list[str]:
        sections: list[str] = []
        for m in self._modules.values():
            sections.extend(m.help_sections())
        return sections
