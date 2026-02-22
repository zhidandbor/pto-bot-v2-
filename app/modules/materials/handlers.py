from __future__ import annotations

from datetime import datetime, timedelta

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
    "<code>[Имя] ([Тип]) - [Количество] [Единицы]</code>\n\n"
    "<b>Пример:</b>\n"
    "<code>ПС 55\n"
    "уголок г/к (50х50х5, L=6 м) - 0,156 т\n"
    "кабель ВВГнг 3х2.5 - 100 м</code>\n\n"
    "Десятичный разделитель: "," или "." (в Excel будет запятая).\n\n"
    "<i>В личном чате укажите объект первой строкой "
    "(например: «ПС 55» или «Левашово»).</i>"
)


def build_router(service: MaterialsService) -> Router:
    r = Router(name="materials")

    @r.message(Command("materials"))
    async def cmd_materials(message: Message, state: FSMContext, **kwargs: object) -> None:
        if message.from_user is None:
            return

        is_group = message.chat.type in ("group", "supergroup")
        scope_id = message.chat.id if is_group else message.from_user.id

        allowed, remaining = await service.check_cooldown(scope_id=scope_id)
        if not allowed:
            minutes, secs = divmod(max(0, remaining), 60)
            until = datetime.now().astimezone() + timedelta(seconds=int(remaining))
            await message.reply(
                "⏱ Следующую заявку на материалы можно отправить через "
                f"{minutes} мин. {secs} сек. (до {until:%H:%M})."
            )
            return

        await state.set_state(MaterialsFSM.waiting_list)
        await message.reply(_INSTRUCTION, parse_mode="HTML")
        logger.info("materials_started", chat_id=message.chat.id, user_id=message.from_user.id)

    @r.message(MaterialsFSM.waiting_list)
    async def on_waiting_non_text(message: Message, **kwargs: object) -> None:
        if not message.text:
            await message.reply("⚠️ Отправьте текст заявки. Каждый материал — с новой строки.")

    @r.message(MaterialsFSM.waiting_list, F.text)
    async def on_materials_list(message: Message, state: FSMContext, **kwargs: object) -> None:
        if message.from_user is None or not message.text:
            return

        is_private = message.chat.type == "private"
        result = await service.build_preview(
            text=message.text,
            chat_id=message.chat.id,
            telegram_user_id=message.from_user.id,
            user_full_name=message.from_user.full_name,
            is_private=is_private,
        )

        if result.hard_error:
            # ВАЖНО: сценарий не завершён — оставляем state, чтобы пользователь мог повторить ввод
            await message.reply(result.hard_error)
            return

        await state.clear()
        await message.reply(
            result.preview_text,
            reply_markup=confirm_cancel_kb(result.draft_id),
        )
        logger.info("materials_preview_sent", draft_id=result.draft_id, user_id=message.from_user.id, chat_id=message.chat.id)

    @r.callback_query(F.data.startswith("mat:confirm:"))
    async def on_confirm(callback: CallbackQuery, **kwargs: object) -> None:
        if callback.from_user is None or callback.message is None:
            await callback.answer("Ошибка данных.", show_alert=True)
            return

        draft_id = (callback.data or "").removeprefix("mat:confirm:")
        if not draft_id:
            await callback.answer("Неверный формат callback.", show_alert=True)
            return

        await callback.answer("Принято, обрабатываю...")
        await callback.message.reply("⏳ Проверяю и формирую заявку...")

        result = await service.confirm(draft_id=draft_id, telegram_user_id=callback.from_user.id)

        if not result.keep_keyboard:
            try:
                await callback.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass

        await callback.message.reply(result.message)
        logger.info("materials_confirm_result", draft_id=draft_id, ok=result.ok, user_id=callback.from_user.id)

    @r.callback_query(F.data.startswith("mat:cancel:"))
    async def on_cancel(callback: CallbackQuery, **kwargs: object) -> None:
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

        msg = await service.cancel(draft_id=draft_id, telegram_user_id=callback.from_user.id)
        await callback.message.reply(msg)
        logger.info("materials_cancel_result", draft_id=draft_id, user_id=callback.from_user.id)

    return r
