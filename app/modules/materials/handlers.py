from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.core.logging import get_logger
from app.modules.materials.fsm import MaterialsFSM
from app.modules.materials.keyboards import confirm_cancel_kb
from app.modules.materials.service import MaterialsService

logger = get_logger(__name__)

_INSTRUCTION = (
    "📦 <b>Заявка на материалы</b>\n\n"
    "Отправьте список материалов — каждый с новой строки:\n\n"
    "<code>[Имя], [Тип], [Количество] [Единицы]</code>\n\n"
    "<b>Пример:</b>\n"
    "<code>уголок г/к, 50х50х5 L=6 м, 0,156 т\n"
    "кабель ВВГнг 3х2.5, 100 м\n"
    "арматура, d8, 300 кг</code>\n\n"
    "Единицы: м, п.м, м², м³, кг, т, шт., компл., уп., рул., л и их варианты.\n\n"
    "<i>В личном чате укажите объект первой строкой "
    "(например: «ПС 55» или «Левашово»).</i>"
)


def build_router(service: MaterialsService) -> Router:
    r = Router(name="materials")

    # ------------------------------------------------------------------
    # /materials — запуск
    # ------------------------------------------------------------------
    @r.message(Command("materials"))
    async def cmd_materials(
        message: Message, state: FSMContext, **kwargs: object
    ) -> None:
        if message.from_user is None:
            return

        is_group = message.chat.type in ("group", "supergroup")
        scope_id = message.chat.id if is_group else message.from_user.id

        allowed, remaining = await service.check_cooldown(scope_id=scope_id)
        if not allowed:
            minutes, secs = divmod(remaining, 60)
            await message.reply(
                f"⏱ Следующую заявку на материалы можно отправить через "
                f"{minutes} мин. {secs} сек."
            )
            return

        await state.set_state(MaterialsFSM.waiting_list)
        await message.reply(_INSTRUCTION, parse_mode="HTML")
        logger.info(
            "materials_started",
            chat_id=message.chat.id,
            user_id=message.from_user.id,
        )

    # ------------------------------------------------------------------
    # Текст заявки в состоянии waiting_list
    # ------------------------------------------------------------------
    @r.message(MaterialsFSM.waiting_list, F.text)
    async def on_materials_list(
        message: Message, state: FSMContext, **kwargs: object
    ) -> None:
        if message.from_user is None or not message.text:
            return

        # Сбрасываем состояние ДО вызова сервиса — пользователь не застрянет в FSM
        await state.clear()

        is_private = message.chat.type == "private"
        result = await service.build_preview(
            text=message.text,
            chat_id=message.chat.id,
            telegram_user_id=message.from_user.id,
            user_full_name=message.from_user.full_name,
            is_private=is_private,
        )

        if result.hard_error:
            await message.reply(result.hard_error)
            return

        await message.reply(
            result.preview_text,
            reply_markup=confirm_cancel_kb(result.draft_id),
        )
        logger.info(
            "materials_preview_sent",
            draft_id=result.draft_id,
            user_id=message.from_user.id,
            chat_id=message.chat.id,
        )

    # ------------------------------------------------------------------
    # Callback: ✅ Подтвердить  (mat:confirm:{draft_id})
    # ------------------------------------------------------------------
    @r.callback_query(F.data.startswith("mat:confirm:"))
    async def on_confirm(
        callback: CallbackQuery, **kwargs: object
    ) -> None:
        if callback.from_user is None or callback.message is None:
            await callback.answer("Ошибка данных.", show_alert=True)
            return

        draft_id = (callback.data or "").removeprefix("mat:confirm:")
        if not draft_id:
            await callback.answer("Неверный формат callback.", show_alert=True)
            return

        # Сразу отвечаем на callback и убираем кнопки (TZ §13.5)
        await callback.answer("Принято, формирую и отправляю...")
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        await callback.message.reply(
            "⏳ Принято. Формирую файл заявки и отправляю на проверку..."
        )

        result = await service.confirm(
            draft_id=draft_id,
            telegram_user_id=callback.from_user.id,
        )
        await callback.message.reply(result.message)
        logger.info(
            "materials_confirm_result",
            draft_id=draft_id,
            ok=result.ok,
            user_id=callback.from_user.id,
        )

    # ------------------------------------------------------------------
    # Callback: ❌ Отменить  (mat:cancel:{draft_id})
    # ------------------------------------------------------------------
    @r.callback_query(F.data.startswith("mat:cancel:"))
    async def on_cancel(
        callback: CallbackQuery, **kwargs: object
    ) -> None:
        if callback.from_user is None or callback.message is None:
            await callback.answer("Ошибка данных.", show_alert=True)
            return

        draft_id = (callback.data or "").removeprefix("mat:cancel:")
        if not draft_id:
            await callback.answer("Неверный формат callback.", show_alert=True)
            return

        await callback.answer("Заявка отменена")
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

        msg = await service.cancel(
            draft_id=draft_id,
            telegram_user_id=callback.from_user.id,
        )
        await callback.message.reply(msg)
        logger.info(
            "materials_cancel_result",
            draft_id=draft_id,
            user_id=callback.from_user.id,
        )

    return r
