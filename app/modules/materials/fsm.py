from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class MaterialsFSM(StatesGroup):
    waiting_list = State()          # ожидание текста заявки после /materials
    waiting_confirmation = State()  # зарезервировано
