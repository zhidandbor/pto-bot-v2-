from __future__ import annotations

import importlib
from dataclasses import dataclass

from app.core.logging import get_logger
from app.core.module_registry import BotModule

logger = get_logger(__name__)


@dataclass(frozen=True)
class ModuleLoader:
    enabled_modules: list[str]

    def load_modules(self, container: object) -> None:
        registry = getattr(container, "registry")
        for mod_name in self.enabled_modules:
            mod_name = mod_name.strip()
            if not mod_name:
                continue
            import_path = f"app.modules.{mod_name}.module"
            try:
                module = importlib.import_module(import_path)
                factory = getattr(module, "create_module")
                bot_module: BotModule = factory(container)
                registry.register_module(bot_module)
                logger.info("module_loaded", module=mod_name)
            except ModuleNotFoundError:
                logger.warning("module_not_found", module=mod_name, import_path=import_path)
            except Exception as e:
                logger.exception("module_load_failed", module=mod_name, error=str(e))