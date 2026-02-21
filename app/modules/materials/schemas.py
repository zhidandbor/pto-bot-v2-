from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class MaterialLine:
    line_no: int
    name: str
    type_mark: str
    qty: float
    unit: str

    def to_dict(self) -> dict:
        return {
            "line_no": self.line_no,
            "name": self.name,
            "type_mark": self.type_mark,
            "qty": self.qty,
            "unit": self.unit,
        }

    def display(self) -> str:
        qty_str = str(int(self.qty)) if self.qty == int(self.qty) else f"{self.qty:.3g}".replace(".", ",")
        mark = f", {self.type_mark}" if self.type_mark else ""
        return f"{self.line_no}. {self.name}{mark} — {qty_str} {self.unit}"


@dataclass
class MaterialDraft:
    draft_id: str
    chat_id: int
    telegram_user_id: int
    object_id: int | None
    ps_number: str | None
    request_date: date
    counter: int
    request_number: str
    recipient_email: str
    user_full_name: str
    lines: list[MaterialLine] = field(default_factory=list)
