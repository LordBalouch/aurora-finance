"""Fingerprints for bank transactions. Pure functions, no Django."""

import hashlib
from collections import Counter
from collections.abc import Iterable

from .importers.base import ParsedRow
from .normalize import clean_description


def fingerprints(rows: Iterable[ParsedRow]) -> list[str]:
    """One fingerprint per row, in order.

    Two genuinely identical purchases on the same day (same amount, same text) are kept apart
    by an occurrence counter, so both are imported once and neither twice on re-import.
    """
    seen: Counter = Counter()
    result = []
    for row in rows:
        key = (
            row.date.isoformat(),
            f"{row.amount:.2f}",
            clean_description(row.description).upper(),
        )
        seen[key] += 1
        raw = "|".join((*key, str(seen[key])))
        result.append(hashlib.sha256(raw.encode()).hexdigest())
    return result
