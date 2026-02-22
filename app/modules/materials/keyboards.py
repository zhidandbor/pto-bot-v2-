from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def confirm_cancel_kb(draft_id: str) -> InlineKeyboardMarkup:
    """Inline-клавиатура предпросмотра: mat:confirm:{id} / mat:cancel:{id} (TZ §13.3)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Подтвердить",
                    callback_data=f"mat:confirm:{draft_id}",
                ),
                InlineKeyboardButton(
                    text="❌ Отменить",
                    callback_data=f"mat:cancel:{draft_id}",
                ),
            ]
        ]
    )
