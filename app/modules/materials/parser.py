from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.logging import get_logger
from app.modules.materials.schemas import MaterialLine
from app.modules.materials.units import normalize_unit

logger = get_logger(__name__)

MAX_LINES = 25
_QTY_RE = re.compile(r"^([\d]+(?:[.,]\d+)?)\s+(.+)$", re.UNICODE)


@dataclass
class ParseResult:
    lines: list[MaterialLine]
    errors: list[str]
    skipped: int


def parse_materials_message(text: str) -> ParseResult:
    """
    Parse message text into MaterialLine list.

    Accepted formats per line:
        название, количество единица
        название, тип/марка, количество единица

    Examples:
        кабель ВВГнг 3х2.5, 100 м
        арматура, d8, 300 кг
        труба, 57х3, 12 м
    """
    raw_lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    raw_lines = [ln for ln in raw_lines if not ln.startswith("/")]

    parsed: list[MaterialLine] = []
    errors: list[str] = []
    skipped = 0

    for raw in raw_lines:
        if len(parsed) >= MAX_LINES:
            skipped += 1
            continue

        parts = [p.strip() for p in raw.split(",")]
        if len(parts) < 2:
            errors.append(f"Нет запятой-разделителя: «{raw[:50]}»")
            continue

        qty_unit_raw = parts[-1].strip()
        name = parts[0].strip()
        type_mark = ", ".join(parts[1:-1]).strip() if len(parts) > 2 else ""

        m = _QTY_RE.match(qty_unit_raw)
        if not m:
            errors.append(f"Формат кол-во/единица: «{qty_unit_raw[:40]}»")
            continue

        qty_str, unit_raw = m.group(1), m.group(2)
        try:
            qty = float(qty_str.replace(",", "."))
        except ValueError:
            errors.append(f"Некорректное число: «{qty_str}»")
            continue

        if qty <= 0:
            errors.append(f"Кол-во должно быть > 0: {qty}")
            continue

        parsed.append(
            MaterialLine(
                line_no=len(parsed) + 1,
                name=name,
                type_mark=type_mark,
                qty=qty,
                unit=normalize_unit(unit_raw),
            )
        )

    logger.debug(
        "parse_result",
        raw=len(raw_lines),
        ok=len(parsed),
        errors=len(errors),
        skipped=skipped,
    )
    return ParseResult(lines=parsed, errors=errors, skipped=skipped)
