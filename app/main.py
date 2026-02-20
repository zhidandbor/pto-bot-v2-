from __future__ import annotations

import asyncio

from aiogram import Dispatcher

from app.core.config import Settings
from app.core.container import build_container
from app.core.logging import configure_logging, get_logger
from app.telegram.bot_factory import build_bot
from app.telegram.middlewares.db_session import DbSessionMiddleware
from app.telegram.middlewares.error_handler import ErrorHandlerMiddleware
from app.telegram.middlewares.rbac import RBACMiddleware
from app.telegram.middlewares.context import ContextResolverMiddleware
from app.telegram.middlewares.rate_limit import RateLimitMiddleware
from app.telegram.routers import admin as admin_router
from app.telegram.routers import superadmin as superadmin_router
from app.telegram.routers import user as user_router
from app.telegram.callbacks import callbacks_router

logger = get_logger(__name__)


async def run_polling() -> None:
    settings = Settings()
    configure_logging(settings)

    container = build_container(settings)

    bot = build_bot(settings)
    dp = Dispatcher()

    dp.update.middleware(ErrorHandlerMiddleware(logger=logger))
    dp.update.middleware(DbSessionMiddleware(session_factory=container.session_factory))
    dp.update.middleware(RBACMiddleware(rbac=container.rbac, registry=container.registry))
    dp.update.middleware(ContextResolverMiddleware(resolver=container.context_resolver, registry=container.registry))
    dp.update.middleware(RateLimitMiddleware(rate_limiter=container.rate_limiter, registry=container.registry))

    dp.include_router(callbacks_router(container))
    dp.include_router(superadmin_router.router(container))
    dp.include_router(admin_router.router(container))
    dp.include_router(user_router.router(container))

    container.module_loader.load_modules(container)

    await container.startup()

    logger.info("bot_start", mode="polling")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await container.shutdown()
        await bot.session.close()


async def run_webhook() -> None:
    from aiohttp import web  # local import to keep polling lightweight
    from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

    settings = Settings()
    configure_logging(settings)

    if not settings.webhook_url:
        raise RuntimeError("WEBHOOK_URL must be set for webhook mode")

    container = build_container(settings)
    bot = build_bot(settings)
    dp = Dispatcher()

    dp.update.middleware(ErrorHandlerMiddleware(logger=logger))
    dp.update.middleware(DbSessionMiddleware(session_factory=container.session_factory))
    dp.update.middleware(RBACMiddleware(rbac=container.rbac, registry=container.registry))
    dp.update.middleware(ContextResolverMiddleware(resolver=container.context_resolver, registry=container.registry))
    dp.update.middleware(RateLimitMiddleware(rate_limiter=container.rate_limiter, registry=container.registry))

    dp.include_router(callbacks_router(container))
    dp.include_router(superadmin_router.router(container))
    dp.include_router(admin_router.router(container))
    dp.include_router(user_router.router(container))

    container.module_loader.load_modules(container)

    await container.startup()

    await bot.set_webhook(settings.webhook_url)

    app = web.Application()
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=settings.webhook_path)
    setup_application(app, dp, bot=bot)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host=settings.webhook_host, port=settings.webhook_port)

    logger.info("bot_start", mode="webhook", host=settings.webhook_host, port=settings.webhook_port)
    try:
        await site.start()
        while True:
            await asyncio.sleep(3600)
    finally:
        await runner.cleanup()
        await container.shutdown()
        await bot.session.close()


def main() -> None:
    settings = Settings()
    if settings.bot_mode == "webhook":
        asyncio.run(run_webhook())
    else:
        asyncio.run(run_polling())


if __name__ == "__main__":
    main()
