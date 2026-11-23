from datetime import date
from decimal import Decimal

import pytest

from ledger.normalize import clean_description, parse_amount, parse_date


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1 234,56", Decimal("1234.56")),
        ("-1.234,56", Decimal("-1234.56")),
        ("1,234.56", Decimal("1234.56")),
        ("1234.56", Decimal("1234.56")),
        ("−50,00", Decimal("-50.00")),
        ("kr 50,00", Decimal("50.00")),
        ("52 300,00", Decimal("52300.00")),
        ("", None),
        (None, None),
    ],
)
def test_parse_amount(text, expected):
    assert parse_amount(text) == expected


def test_parse_amount_rejects_text():
    with pytest.raises(ValueError):
        parse_amount("abc")


@pytest.mark.parametrize(
    "text", ["21.11.2026", "2026-11-21", "2026/11/21", "21/11/2026", "21.11.26"]
)
def test_parse_date(text):
    assert parse_date(text) == date(2026, 11, 21)


@pytest.mark.parametrize(
    ("raw", "clean"),
    [
        ("VISA VAREKJØP *4821 20.11 REMA 1000 STORO Kurs: 1.0000", "REMA 1000 STORO"),
        ("Varekjøp KIWI 505 BISLETT Dato 19.11 kl. 14.03", "KIWI 505 BISLETT"),
        ("NETFLIX.COM", "NETFLIX.COM"),
        ("Visa  100021  Norsk Tipping Abonnement", "Norsk Tipping Abonnement"),
        ("Visa  100022  Nok 79,00 Apple.com/bill", "Apple.com/bill"),
        ("Visa  100022  Eur 23,00 Openai :chatgpt SubValutakurs: 12,0791", "Openai :chatgpt Sub"),
        (
            "Varekjøp Meny Union Bryg Grønland 43 Dramme Dato 01.11 kl. 15.32",
            "Meny Union Bryg Grønland 43 Dramme",
        ),
        ("Lønn ACME AS", "Lønn ACME AS"),
    ],
)
def test_clean_description(raw, clean):
    assert clean_description(raw) == clean
