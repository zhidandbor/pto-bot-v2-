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
    "\U0001f4e6 <b>\u0417\u0430\u044f\u0432\u043a\u0430 \u043d\u0430 \u043c\u0430\u0442\u0435\u0440\u0438\u0430\u043b\u044b</b>\n\n"
    "\u041e\u0442\u043f\u0440\u0430\u0432\u044c\u0442\u0435 \u0441\u043f\u0438\u0441\u043e\u043a \u043c\u0430\u0442\u0435\u0440\u0438\u0430\u043b\u043e\u0432 \u2014 \u043a\u0430\u0436\u0434\u044b\u0439 \u0441 \u043d\u043e\u0432\u043e\u0439 \u0441\u0442\u0440\u043e\u043a\u0438:\n\n"
    "<code>[\u0418\u043c\u044f] ([\u0422\u0438\u043f]) - [\u041a\u043e\u043b\u0438\u0447\u0435\u0441\u0442\u0432\u043e] [\u0415\u0434\u0438\u043d\u0438\u0446\u044b]</code>\n\n"
    "<b>\u041f\u0440\u0438\u043c\u0435\u0440:</b>\n"
    "<code>\u041f\u0421 55\n"
    "\u0443\u0433\u043e\u043b\u043e\u043a \u0433/\u043a (50\u04505, L=6 \u043c) - 0,156 \u0442\n"
    "\u043a\u0430\u0431\u0435\u043b\u044c \u0412\u0412\u0413\u043d\u0433 3\u04502.5 - 100 \u043c</code>\n\n"
    "<i>\u0412 \u043b\u0438\u0447\u043d\u043e\u043c \u0447\u0430\u0442\u0435 \u0443\u043a\u0430\u0436\u0438\u0442\u0435 \u043e\u0431\u044a\u0435\u043a\u0442 \u043f\u0435\u0440\u0432\u043e\u0439 \u0441\u0442\u0440\u043e\u043a\u043e\u0439 "
    "(\u043d\u0430\u043f\u0440\u0438\u043c\u0435\u0440: \u00ab\u041f\u0421 55\u00bb \u0438\u043b\u0438 \u00ab\u041b\u0435\u0432\u0430\u0448\u043e\u0432\u0441\u043a\u0430\u044f\u00bb).</i>"
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
                "\u23f1 \u0421\u043b\u0435\u0434\u0443\u044e\u0449\u0443\u044e \u0437\u0430\u044f\u0432\u043a\u0443 \u043d\u0430 \u043c\u0430\u0442\u0435\u0440\u0438\u0430\u043b\u044b \u043c\u043e\u0436\u043d\u043e \u043e\u0442\u043f\u0440\u0430\u0432\u0438\u0442\u044c \u0447\u0435\u0440\u0435\u0437 "
                f"{minutes} \u043c\u0438\u043d. {secs} \u0441\u0435\u043a. (\u0434\u043e {until:%H:%M})."
            )
            return

        await state.set_state(MaterialsFSM.waiting_list)
        await message.reply(_INSTRUCTION, parse_mode="HTML")
        logger.info("materials_started", chat_id=message.chat.id, user_id=message.from_user.id)

    # FIX BUG-3: In aiogram 3 handlers are matched strictly in registration order.
    # The handler with the MORE SPECIFIC filter (F.text) MUST be registered FIRST.
    # Previously on_waiting_non_text (no filter = matches everything including text)
    # was registered before on_materials_list (F.text), silently consuming all text
    # messages in waiting_list state without calling on_materials_list at all.

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
            # Scenario not completed — keep state so user can retry input
            await message.reply(result.hard_error)
            return

        await state.clear()
        await message.reply(
            result.preview_text,
            reply_markup=confirm_cancel_kb(result.draft_id),
        )
        logger.info("materials_preview_sent", draft_id=result.draft_id, user_id=message.from_user.id, chat_id=message.chat.id)

    @r.message(MaterialsFSM.waiting_list, ~F.text)
    async def on_waiting_non_text(message: Message, **kwargs: object) -> None:
        await message.reply("\u26a0\ufe0f \u041e\u0442\u043f\u0440\u0430\u0432\u044c\u0442\u0435 \u0442\u0435\u043a\u0441\u0442 \u0437\u0430\u044f\u0432\u043a\u0438. \u041a\u0430\u0436\u0434\u044b\u0439 \u043c\u0430\u0442\u0435\u0440\u0438\u0430\u043b \u2014 \u0441 \u043d\u043e\u0432\u043e\u0439 \u0441\u0442\u0440\u043e\u043a\u0438.")

    @r.callback_query(F.data.startswith("mat:confirm:"))
    async def on_confirm(callback: CallbackQuery, **kwargs: object) -> None:
        if callback.from_user is None or callback.message is None:
            await callback.answer("\u041e\u0448\u0438\u0431\u043a\u0430 \u0434\u0430\u043d\u043d\u044b\u0445.", show_alert=True)
            return

        draft_id = (callback.data or "").removeprefix("mat:confirm:")
        if not draft_id:
            await callback.answer("\u041d\u0435\u0432\u0435\u0440\u043d\u044b\u0439 \u0444\u043e\u0440\u043c\u0430\u0442 callback.", show_alert=True)
            return

        await callback.answer("\u041f\u0440\u0438\u043d\u044f\u0442\u043e, \u043e\u0431\u0440\u0430\u0431\u0430\u0442\u044b\u0432\u0430\u044e...")
        await callback.message.reply("\u23f3 \u041f\u0440\u043e\u0432\u0435\u0440\u044f\u044e \u0438 \u0444\u043e\u0440\u043c\u0438\u0440\u0443\u044e \u0437\u0430\u044f\u0432\u043a\u0443...")

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
            await callback.answer("\u041e\u0448\u0438\u0431\u043a\u0430 \u0434\u0430\u043d\u043d\u044b\u0445.", show_alert=True)
            return

        draft_id = (callback.data or "").removeprefix("mat:cancel:")
        if not draft_id:
            await callback.answer("\u041d\u0435\u0432\u0435\u0440\u043d\u044b\u0439 \u0444\u043e\u0440\u043c\u0430\u0442 callback.", show_alert=True)
            return

        await callback.answer("\u0417\u0430\u044f\u0432\u043a\u0430 \u043e\u0442\u043c\u0435\u043d\u0435\u043d\u0430")
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

        msg = await service.cancel(draft_id=draft_id, telegram_user_id=callback.from_user.id)
        await callback.message.reply(msg)
        logger.info("materials_cancel_result", draft_id=draft_id, user_id=callback.from_user.id)

    return r
