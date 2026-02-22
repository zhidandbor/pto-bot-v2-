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

_QTY_UNIT_RE = re.compile(
    r"^\s*([0-9]+(?:[.,][0-9]+)?)\s*(?:[-\u2013\u2014]\s*([0-9]+(?:[.,][0-9]+)?))?\s*(.+?)\s*$",
    re.UNICODE,
)

_TRAILING_JUNK_RE = re.compile(r"[ \t]*[.:;]+[ \t]*$", re.UNICODE)

_NAME_TYPE_RE = re.compile(r"^\s*(.+?)\s*\((.+?)\)\s*$", re.UNICODE)


@dataclass
class ParseResult:
    lines: list[MaterialLine]
    errors: list[str]
    skipped: int


def _normalize_raw_line(s: str) -> str:
    s = s.strip()
    if not s or s.startswith("/"):
        return ""
    s = s.replace("\u2014", "-").replace("\u2013", "-")
    s = _TRAILING_JUNK_RE.sub("", s)
    s = re.sub(r"\s+", " ", s, flags=re.UNICODE)
    return s


def _to_decimal(num: str) -> Decimal:
    return Decimal(num.replace(",", "."))


def _split_head_qty_unit(raw: str) -> tuple[str, str] | None:
    """Split line into (head, qty_unit_tail) without breaking decimal comma."""
    tokens = raw.split()
    if not tokens:
        return None

    # Try 1..3 trailing tokens as qty+unit segment.
    for n in (3, 2, 1):
        if len(tokens) < n:
            continue
        tail = " ".join(tokens[-n:]).strip()
        # allow leading ≈ or ~
        tail_norm = tail.lstrip("\u2248~ ").strip()
        if not tail_norm:
            continue
        if not re.match(r"^[0-9]", tail_norm):
            continue
        if _QTY_UNIT_RE.match(tail_norm):
            head = " ".join(tokens[:-n]).strip().strip(",;-")
            return head, tail_norm

    return None


def parse_materials_message(text: str) -> ParseResult:
    """Parse materials list.

    Preferred format per line:
        [Имя] ([Тип]) - [Количество] [Единицы]

    Also accepted (for user mistakes):
        [Имя] - [Количество] [Единицы]
        [Имя], [Тип], [Количество] [Единицы]
        [Имя], [Количество] [Единицы]

    Quantity accepts "," or "." as decimal separator and ranges A-B (upper bound used).
    """
    if len(text) > MAX_TEXT_CHARS:
        return ParseResult(lines=[], errors=[f"Сообщение слишком длинное (>{MAX_TEXT_CHARS} символов)."], skipped=0)

    raw_lines = [_normalize_raw_line(ln) for ln in text.splitlines()]
    raw_lines = [ln for ln in raw_lines if ln and not ln.startswith("/")]

    parsed: list[MaterialLine] = []
    errors: list[str] = []
    skipped = 0

    for raw in raw_lines:
        if len(parsed) >= MAX_LINES:
            skipped += 1
            continue

        split_res = _split_head_qty_unit(raw)
        if split_res is None:
            errors.append(f"Формат строки: \u00ab{raw[:60]}\u00bb")
            continue

        head, qty_unit_raw = split_res
        head = (head or "").strip().rstrip(",")

        # parse qty+unit
        qty_unit_raw = qty_unit_raw.lstrip("\u2248~ ").strip()
        m = _QTY_UNIT_RE.match(qty_unit_raw)
        if not m:
            errors.append(f"Формат кол-во/единица: \u00ab{qty_unit_raw[:40]}\u00bb")
            continue

        qty_left, qty_right, unit_raw = m.group(1), m.group(2), m.group(3)

        try:
            qty = _to_decimal(qty_right or qty_left)
        except (InvalidOperation, ValueError):
            errors.append(f"Некорректное число: \u00ab{qty_right or qty_left}\u00bb")
            continue

        if qty <= 0:
            errors.append(f"Кол-во должно быть > 0: {qty}")
            continue

        name = ""
        type_mark = ""

        # Preferred: name (type)
        mt = _NAME_TYPE_RE.match(head)
        if mt:
            name = mt.group(1).strip()
            type_mark = mt.group(2).strip()
        else:
            # Fallback: comma-separated head
            parts = [p.strip() for p in head.split(",") if p.strip()]
            if not parts:
                errors.append(f"Нет наименования: \u00ab{raw[:60]}\u00bb")
                continue
            name = parts[0]
            type_mark = ", ".join(parts[1:]).strip() if len(parts) > 1 else ""

        parsed.append(
            MaterialLine(
                line_no=len(parsed) + 1,
                name=name,
                type_mark=type_mark,
                qty=qty,
                unit=normalize_unit(unit_raw),
            )
        )

    logger.debug("parse_result", raw=len(raw_lines), ok=len(parsed), errors=len(errors), skipped=skipped)
    return ParseResult(lines=parsed, errors=errors, skipped=skipped)
