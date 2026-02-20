from __future__ import annotations

from aiogram import Router
from aiogram.types import CallbackQuery

from app.core.logging import get_logger

logger = get_logger(__name__)


def callbacks_router(container: object) -> Router:  # type: ignore[type-arg]
    r = Router(name="callbacks")

    @r.callback_query(lambda c: bool(c.data) and c.data.startswith("ctx_select:"))
    async def on_context_select(callback: CallbackQuery, **kwargs: object) -> None:
        session = kwargs["session"]
        parts = (callback.data or "").split(":")
        if len(parts) != 3:
            await callback.answer("Ошибка данных.", show_alert=True)
            return
        try:
            object_id = int(parts[1])
            chat_id = int(parts[2])
        except ValueError:
            await callback.answer("Ошибка данных.", show_alert=True)
            return

        user_id = callback.from_user.id
        await container.context_resolver.set_context(  # type: ignore[attr-defined]
            session, user_id=user_id, chat_id=chat_id, object_id=object_id
        )
        obj = await container.objects_repo.get_by_id(session, object_id)  # type: ignore[attr-defined]
        title = obj.title if obj else str(object_id)
        await callback.answer(f"\u2705 Выбран: {title}")
        if callback.message:
            await callback.message.edit_reply_markup(reply_markup=None)
        logger.info("context_selected", user_id=user_id, chat_id=chat_id, object_id=object_id)

    return r
