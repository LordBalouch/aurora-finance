from decimal import Decimal

import pytest

from ledger.categorize import Matcher, RuleSpec, TxnView, merchant_key


@pytest.mark.parametrize(
    ("text", "key"),
    [
        ("Overføring Innland 3947 Kari Nordmann Takk For Maten", "kari nordmann"),
        ("Kiwi 332 Xl Lig Betzy Kjelsb Dramme", "kiwi xl"),
        ("100021 Vipps:apcoa Flow", "apcoa flow"),
        ("Overføring 12345678903 Ola Nordmann Veide Ikke Tpp: Vipps Mobilepay AS", "ola nordmann"),
        ("Giro 2789 Santander Consumer Bank Efaktura", "santander consumer"),
        ("Varekjøp Med Kib Meny Brakerøya Brantenborgg", "meny brakerøya"),
        ("Apple.com/bill", "apple.com bill"),
    ],
)
def test_merchant_key(text, key):
    assert merchant_key(text) == key


def rule(id, pattern, match="word", sign="any", priority=50, cat=1):
    return RuleSpec(id, pattern, match, sign, priority, cat)


def txn(text, amount, merchant=""):
    return TxnView(text, merchant or merchant_key(text), Decimal(amount))


def test_word_match_needs_whole_words():
    m = Matcher([rule(1, "SPAR")])
    assert m.match(txn("Varekjøp Spar Torget Oslo", "-10"))
    assert m.match(txn("Sparebank 1 overføring", "-10")) is None


def test_priority_beats_order_and_longest_pattern_breaks_ties():
    m = Matcher(
        [
            rule(1, "KIWI", cat=1),
            rule(2, "MED KIB", priority=80, cat=2),
            rule(3, "OBS", cat=3),
            rule(4, "OBS BYGG", cat=4),
        ]
    )
    assert m.match(txn("Varekjøp Med Kib Kiwi 332", "-5000")).category_id == 2
    assert m.match(txn("Varekjøp Kiwi 332", "-50")).category_id == 1
    assert m.match(txn("Varekjøp Obs Bygg Mjøndalen", "-50")).category_id == 4


def test_sign_filter():
    m = Matcher([rule(1, "NAV", sign="in", cat=1), rule(2, "NAV", sign="out", cat=2)])
    assert m.match(txn("Overføring Innland Nav", "1000")).category_id == 1
    assert m.match(txn("Overføring Innland Nav", "-1000")).category_id == 2


def test_merchant_rule_is_exact_and_case_insensitive():
    m = Matcher([rule(1, "Kari Nordmann", match="merchant")])
    assert m.match(txn("Overføring Innland 3966 Kari Nordmann Pinnekjøtt", "280"))
    assert m.match(txn("Overføring Innland Kari Hansen", "280")) is None


def test_regex_and_contains():
    m = Matcher(
        [rule(1, r"^LØNN\b", match="regex", cat=1), rule(2, "APPLE.COM", "contains", cat=2)]
    )
    assert m.match(txn("Lønn 55140083466 Indre Østfold Kommune", "20000")).category_id == 1
    assert m.match(txn("Visa 100022 Nok 79,00 Apple.com/bill", "-79")).category_id == 2
