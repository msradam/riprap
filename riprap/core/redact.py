"""Remove email addresses and phone numbers from fetched records (refactor 6).

311 free text (Albany SeeClickFix summaries and descriptions, a Socrata
feed's notes fields) sometimes holds a resident's email or phone number. The 311 adapters pass every
fetched payload through `redact` before it reaches a briefing, a cache, a
log or a file.

Names are not removed: telling a name from a street or an agency needs
more than a pattern, and a wrong guess would damage the text.
"""

from __future__ import annotations

import re
from typing import Any

EMAIL = "[email removed]"
PHONE = "[phone removed]"

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# A North American number written with separators: (617) 555-0123,
# 617-555-0123, 617.555.0123, +1 617 555 0123.
_PHONE_SEP_RE = re.compile(r"(?<![\w.-])(?:\+?1[\s.-]?)?(?:\(\d{3}\)\s?|\d{3}[\s.-])\d{3}[\s.-]\d{4}(?![\w-])")
# Ten or eleven bare digits, only inside free text (a string with a space),
# so a single-token record id is never touched.
_PHONE_BARE_RE = re.compile(r"(?<![\w.,-])(?:1)?[2-9]\d{2}[2-9]\d{6}(?![\w-]|[.,]\d)")


def redact_text(s: str) -> str:
    s = _EMAIL_RE.sub(EMAIL, s)
    s = _PHONE_SEP_RE.sub(PHONE, s)
    return _PHONE_BARE_RE.sub(PHONE, s) if " " in s else s


def redact(value: Any) -> Any:
    """The same structure with every string redacted."""
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, dict):
        return {k: redact(v) for k, v in value.items()}
    return value
