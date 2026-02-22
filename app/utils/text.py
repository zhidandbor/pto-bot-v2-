from __future__ import annotations

import re

_ws_re = re.compile(r"\s+", flags=re.UNICODE)


def norm_str(value: str) -> str:
    """
    Normalizes header-like strings for Excel import:
    - strip
    - collapse whitespace
    - lowercase
    """
    s = (value or "").strip()
    s = _ws_re.sub(" ", s)
    return s.lower()
