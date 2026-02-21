from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


@dataclass
class MaterialLine:
    line_no: int
    name: str
    type_mark: str
    qty: Decimal
    unit: str

    def to_dict(self) -> dict:
        # Decimal не JSON-serializable → храним строкой без потери точности
        return {
            "line_no": self.line_no,
            "name": self.name,
            "type_mark": self.type_mark,
            "qty": str(self.qty),
            "unit": self.unit,
        }

    def display(self) -> str:
        q = self.qty
        if q == q.to_integral_value():
            qty_str = str(int(q))
        else:
            qty_str = format(q.normalize(), "f").rstrip("0").rstrip(".").replace(".", ",")
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
