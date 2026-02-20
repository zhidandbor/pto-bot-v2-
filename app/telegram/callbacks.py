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

        # Structural guard
        if callback.message is None or callback.from_user is None:
            await callback.answer("Ошибка: нет данных чата.", show_alert=True)
            return

        # Security: take chat_id from the ACTUAL message, not from callback_data.
        # Prevents a user forging chat_id to set context in an arbitrary chat.
        actual_chat_id: int = callback.message.chat.id
        is_group: bool = callback.message.chat.type in ("group", "supergroup")
        user_id: int = callback.from_user.id

        # Parse object_id only (discard chat_id from callback_data entirely).
        parts = (callback.data or "").split(":")
        if len(parts) != 3:
            await callback.answer("Ошибка данных.", show_alert=True)
            return
        try:
            object_id = int(parts[1])
        except ValueError:
            await callback.answer("Ошибка данных.", show_alert=True)
            return

        # Validate object_id is accessible for this chat/user before writing.
        if is_group:
            linked = await container.objects_repo.list_linked_objects(session, actual_chat_id)  # type: ignore[attr-defined]
            valid_ids = {o.id for o in linked}
        else:
            obj_check = await container.objects_repo.get_by_id(session, object_id)  # type: ignore[attr-defined]
            valid_ids = {obj_check.id} if obj_check else set()

        if object_id not in valid_ids:
            await callback.answer("\u26d4 Объект недоступен.", show_alert=True)
            logger.warning(
                "ctx_select_invalid_object",
                user_id=user_id,
                chat_id=actual_chat_id,
                object_id=object_id,
            )
            return

        await container.context_resolver.set_context(  # type: ignore[attr-defined]
            session, user_id=user_id, chat_id=actual_chat_id, object_id=object_id
        )

        obj = await container.objects_repo.get_by_id(session, object_id)  # type: ignore[attr-defined]
        title = (
            obj.title_name or obj.ps_name or f"#{object_id}"
        ) if obj else str(object_id)
        await callback.answer(f"\u2705 Выбран: {title}")
        if callback.message:
            await callback.message.edit_reply_markup(reply_markup=None)
        logger.info(
            "context_selected",
            user_id=user_id,
            chat_id=actual_chat_id,
            object_id=object_id,
        )

    return r
