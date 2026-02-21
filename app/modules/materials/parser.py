from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from app.core.logging import get_logger
from app.modules.materials.schemas import MaterialLine
from app.modules.materials.units import normalize_unit

logger = get_logger(__name__)

MAX_LINES = 25
MAX_TEXT_CHARS = 20_000

# qty: 10 | 10.5 | 10,5 | 10-12 | 10 – 12 | 100м (слитно) → единица захватывается третьей группой
_QTY_UNIT_RE = re.compile(
    r"^\s*([0-9]+(?:[.,][0-9]+)?)\s*(?:[-\u2013\u2014]\s*([0-9]+(?:[.,][0-9]+)?))?\s*(.+?)\s*$",
    re.UNICODE,
)

_TRAILING_JUNK_RE = re.compile(r"[ \t]*[.:;]+[ \t]*$", re.UNICODE)


@dataclass
class ParseResult:
    lines: list[MaterialLine]
    errors: list[str]
    skipped: int


def _normalize_raw_line(s: str) -> str:
    s = s.strip()
    if not s or s.startswith("/"):
        return ""
    # унифицировать разные тире в ASCII-дефис
    s = s.replace("\u2014", "-").replace("\u2013", "-")
    # убрать хвостовую пунктуацию (точки/двоеточия/точка с запятой)
    s = _TRAILING_JUNK_RE.sub("", s)
    # схлопнуть пробелы
    s = re.sub(r"\s+", " ", s, flags=re.UNICODE)
    return s


def _to_decimal(num: str) -> Decimal:
    return Decimal(num.replace(",", "."))


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
        кабель, 100м          ← слитно — принимается
        труба, 10-12 м        ← диапазон → берётся верхняя граница
        арматура, ≈300 кг     ← приближённое → принимается
    """
    if len(text) > MAX_TEXT_CHARS:
        return ParseResult(
            lines=[],
            errors=[f"Сообщение слишком длинное (>{MAX_TEXT_CHARS} символов)."],
            skipped=0,
        )

    raw_lines = [_normalize_raw_line(ln) for ln in text.splitlines()]
    raw_lines = [ln for ln in raw_lines if ln and not ln.startswith("/")]

    parsed: list[MaterialLine] = []
    errors: list[str] = []
    skipped = 0

    for raw in raw_lines:
        if len(parsed) >= MAX_LINES:
            skipped += 1
            continue

        parts = [p.strip() for p in raw.split(",") if p.strip()]
        if len(parts) < 2:
            errors.append(f"Нет запятой-разделителя: \u00ab{raw[:50]}\u00bb")
            continue

        qty_unit_raw = parts[-1].strip()
        name = parts[0].strip()
        type_mark = ", ".join(parts[1:-1]).strip() if len(parts) > 2 else ""

        # допускаем лидирующие ≈/~ перед количеством
        qty_unit_raw = qty_unit_raw.lstrip("\u2248~ ").strip()

        m = _QTY_UNIT_RE.match(qty_unit_raw)
        if not m:
            errors.append(f"Формат кол-во/единица: \u00ab{qty_unit_raw[:40]}\u00bb")
            continue

        qty_left, qty_right, unit_raw = m.group(1), m.group(2), m.group(3)

        try:
            # диапазон A-B → берём верхнюю границу B; иначе A
            qty = _to_decimal(qty_right or qty_left)
        except (InvalidOperation, ValueError):
            errors.append(f"Некорректное число: \u00ab{qty_right or qty_left}\u00bb")
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
