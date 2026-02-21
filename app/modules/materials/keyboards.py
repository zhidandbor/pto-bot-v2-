from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def confirm_cancel_kb(draft_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="\u2705 Отправить",
                    callback_data=f"matconfirm{draft_id}",
                ),
                InlineKeyboardButton(
                    text="\u274c Отменить",
                    callback_data=f"matcancel{draft_id}",
                ),
            ]
        ]
    )
