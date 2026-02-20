from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.core.module_loader import ModuleLoader
from app.core.module_registry import CommandSpec, ModuleRegistry
from app.core.logging import get_logger
from app.db.session import make_session_factory
from app.db.repositories.admins import AdminRepository
from app.db.repositories.audit_log import AuditLogRepository
from app.db.repositories.excel_imports import ExcelImportsRepository
from app.db.repositories.groups import GroupsRepository
from app.db.repositories.objects import ObjectsRepository
from app.db.repositories.rate_limits import RateLimitsRepository
from app.db.repositories.settings import SettingsRepository
from app.db.repositories.user_contexts import UserContextsRepository
from app.db.repositories.users import UsersRepository
from app.services.admin_service import AdminService
from app.services.audit_service import AuditService
from app.services.context_resolver import ContextResolver
from app.services.excel_import_service import ExcelImportService
from app.services.help_service import HelpService
from app.services.rate_limiter import RateLimiter
from app.services.rbac import RBACService
from app.services.settings_service import SettingsService
from app.integrations.excel_reader import ExcelReader
from app.integrations.smtp_mailer import SmtpMailer

logger = get_logger(__name__)


@dataclass
class Container:
    settings: Settings
    engine: AsyncEngine
    session_factory: async_sessionmaker

    registry: ModuleRegistry
    module_loader: ModuleLoader

    users_repo: UsersRepository
    admins_repo: AdminRepository
    groups_repo: GroupsRepository
    objects_repo: ObjectsRepository
    settings_repo: SettingsRepository
    rate_limits_repo: RateLimitsRepository
    audit_repo: AuditLogRepository
    excel_imports_repo: ExcelImportsRepository
    user_contexts_repo: UserContextsRepository

    settings_service: SettingsService
    audit_service: AuditService
    rbac: RBACService
    context_resolver: ContextResolver
    rate_limiter: RateLimiter
    admin_service: AdminService
    help_service: HelpService
    excel_import_service: ExcelImportService

    mailer: SmtpMailer
    excel_reader: ExcelReader

    async def startup(self) -> None:
        await self.settings_service.ensure_defaults()
        logger.info("startup_done")

    async def shutdown(self) -> None:
        await self.engine.dispose()


def build_container(settings: Settings) -> Container:
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    session_factory = make_session_factory(engine)

    registry = ModuleRegistry()

    core_commands = [
        CommandSpec("start", "О боте", "user", False, False),
        CommandSpec("sart", "О боте (алиас)", "user", False, False),
        CommandSpec("help", "Справка", "user", False, False),
        CommandSpec("object_search", "Поиск объекта (личка)", "user", False, False),
        CommandSpec("object_import", "Импорт объектов из Excel", "admin", False, False),
        CommandSpec("recipient_email", "Установить email получателя", "admin", False, False),
        CommandSpec("time", "Установить cooldown (мин)", "admin", False, False),
        CommandSpec("object_list", "Список объектов", "admin", False, False),
        CommandSpec("object_add", "Добавить объект", "admin", False, False),
        CommandSpec("object_del", "Удалить объект", "admin", False, False),
        CommandSpec("group_add", "Привязать группу к объекту", "admin", False, False),
        CommandSpec("group_del", "Удалить привязку группы", "admin", False, False),
        CommandSpec("group_list", "Список привязок", "admin", False, False),
        CommandSpec("user_add", "Разрешить пользователя в личке", "admin", False, False),
        CommandSpec("user_del", "Запретить пользователя в личке", "admin", False, False),
        CommandSpec("user_list", "Список разрешённых пользователей", "admin", False, False),
        CommandSpec("admin_add", "Добавить администратора", "superadmin", False, False),
        CommandSpec("admin_del", "Удалить администратора", "superadmin", False, False),
        CommandSpec("admin_list", "Список администраторов", "superadmin", False, False),
        CommandSpec("module", "Команда модуля (вызов)", "user", True, True),
        CommandSpec("knowledge", "Команда базы знаний (пример)", "user", True, False, rate_limit_exempt=True),
    ]
    for spec in core_commands:
        registry._commands[spec.command] = spec  # internal registration of core commands

    enabled = []  # modules are loaded only when present/configured
    module_loader = ModuleLoader(enabled_modules=enabled)

    users_repo = UsersRepository()
    admins_repo = AdminRepository()
    groups_repo = GroupsRepository()
    objects_repo = ObjectsRepository()
    settings_repo = SettingsRepository()
    rate_limits_repo = RateLimitsRepository()
    audit_repo = AuditLogRepository()
    excel_imports_repo = ExcelImportsRepository()
    user_contexts_repo = UserContextsRepository()

    settings_service = SettingsService(settings=settings, repo=settings_repo)
    audit_service = AuditService(repo=audit_repo)
    rbac = RBACService(settings=settings, admins_repo=admins_repo, users_repo=users_repo)
    context_resolver = ContextResolver(
        settings=settings,
        objects_repo=objects_repo,
        groups_repo=groups_repo,
        links_repo=objects_repo,
        user_contexts_repo=user_contexts_repo,
        rbac=rbac,
    )
    rate_limiter = RateLimiter(settings=settings, settings_service=settings_service, repo=rate_limits_repo)

    mailer = SmtpMailer(settings=settings)
    excel_reader = ExcelReader()

    admin_service = AdminService(
        settings=settings,
        users_repo=users_repo,
        admins_repo=admins_repo,
        groups_repo=groups_repo,
        objects_repo=objects_repo,
        settings_service=settings_service,
        audit=audit_service,
    )
    help_service = HelpService(registry=registry, rbac=rbac, settings_service=settings_service)
    excel_import_service = ExcelImportService(
        settings=settings,
        reader=excel_reader,
        objects_repo=objects_repo,
        excel_imports_repo=excel_imports_repo,
        audit=audit_service,
    )

    return Container(
        settings=settings,
        engine=engine,
        session_factory=session_factory,
        registry=registry,
        module_loader=module_loader,
        users_repo=users_repo,
        admins_repo=admins_repo,
        groups_repo=groups_repo,
        objects_repo=objects_repo,
        settings_repo=settings_repo,
        rate_limits_repo=rate_limits_repo,
        audit_repo=audit_repo,
        excel_imports_repo=excel_imports_repo,
        user_contexts_repo=user_contexts_repo,
        settings_service=settings_service,
        audit_service=audit_service,
        rbac=rbac,
        context_resolver=context_resolver,
        rate_limiter=rate_limiter,
        admin_service=admin_service,
        help_service=help_service,
        excel_import_service=excel_import_service,
        mailer=mailer,
        excel_reader=excel_reader,
    )
