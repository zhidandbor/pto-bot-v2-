from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def confirm_cancel_kb(draft_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Отправить",
                    callback_data=f"mat_confirm:{draft_id}",
                ),
                InlineKeyboardButton(
                    text="❌ Отменить",
                    callback_data=f"mat_cancel:{draft_id}",
                ),
            ]
        ]
    )
