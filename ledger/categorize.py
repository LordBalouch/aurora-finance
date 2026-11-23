"""Merchant keys and rule matching. Pure functions, no Django."""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

_PREFIX = re.compile(
    r"^(?:(?:ubetjent\s+)?varekjøp(?:\s+med\s+kib)?|overføring(?:\s+innland)?|kontoregulering"
    r"|giro|lønn|autogiro|visa|zettle_:|paypal_:|vipps:|sumup\s*:|nyx:|ubr:)\s*",
    re.IGNORECASE,
)
_TAIL = re.compile(r"\s*(?:tpp:.*|ref:.*|isref:.*)$", re.IGNORECASE)
_TOKEN = re.compile(r"[^\W\d_][\w.&'-]*", re.UNICODE)


def merchant_key(description: str, words: int = 2) -> str:
    """'Overføring Innland 3947 Kari Nordmann Takk For Maten' -> 'kari nordmann'.

    Groups the same merchant or person across transactions, for the inbox and user rules.
    """
    s = _TAIL.sub("", description.strip())
    for _ in range(3):  # prefixes can stack: 'Visa 100021 Vipps:apcoa Flow'
        s = re.sub(r"^\d+\s*", "", _PREFIX.sub("", s).strip())
    tokens = [t.lower() for t in _TOKEN.findall(s)]
    return " ".join(tokens[:words])


@dataclass(frozen=True)
class RuleSpec:
    id: int
    pattern: str
    match: str  # word | contains | regex | merchant
    sign: str  # any | in | out
    priority: int
    category_id: int


@dataclass(frozen=True)
class TxnView:
    text: str  # raw bank text
    merchant: str
    amount: Decimal


def _compile(rule: RuleSpec):
    if rule.match == "merchant":
        return None
    if rule.match == "regex":
        return re.compile(rule.pattern, re.IGNORECASE)
    if rule.match == "contains":
        return re.compile(re.escape(rule.pattern), re.IGNORECASE)
    return re.compile(rf"(?<!\w){re.escape(rule.pattern)}(?!\w)", re.IGNORECASE)


class Matcher:
    def __init__(self, rules: Iterable[RuleSpec]):
        ordered = sorted(rules, key=lambda r: (-r.priority, -len(r.pattern), r.id))
        self._rules = [(r, _compile(r)) for r in ordered]

    def match(self, txn: TxnView) -> RuleSpec | None:
        direction = "in" if txn.amount > 0 else "out"
        for rule, regex in self._rules:
            if rule.sign != "any" and rule.sign != direction:
                continue
            if regex is None:
                if txn.merchant == rule.pattern.lower():
                    return rule
            elif regex.search(txn.text):
                return rule
        return None
