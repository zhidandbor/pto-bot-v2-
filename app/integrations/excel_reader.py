from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, datetime
from io import BytesIO
from typing import Any

import openpyxl

from app.utils.text import norm_str


@dataclass(frozen=True)
class ExcelRow:
    fields: dict[str, Any]


class ExcelReader:
    async def read_objects(self, xlsx_bytes: bytes) -> list[ExcelRow]:
        return await asyncio.to_thread(self._read_objects_sync, xlsx_bytes)

    def _read_objects_sync(self, xlsx_bytes: bytes) -> list[ExcelRow]:
        wb = openpyxl.load_workbook(BytesIO(xlsx_bytes), data_only=True)
        ws = wb.active

        headers: dict[int, str] = {}
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return []

        header_row = rows[0]
        for idx, cell in enumerate(header_row):
            h = norm_str(str(cell) if cell is not None else "")
            if not h:
                continue
            headers[idx] = h

        mapped: list[ExcelRow] = []
        for r in rows[1:]:
            if r is None:
                continue
            data: dict[str, Any] = {}
            empty = True
            for idx, value in enumerate(r):
                key = headers.get(idx)
                if not key:
                    continue
                if value is not None and str(value).strip() != "":
                    empty = False
                data[key] = value
            if empty:
                continue
            mapped.append(ExcelRow(fields=data))
        return mapped
