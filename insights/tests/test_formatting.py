from decimal import Decimal

import pytest

from insights.formatting import MINUS, THIN_SPACE, format_nok, percent_change


@pytest.mark.parametrize(
    ("amount", "decimals", "expected"),
    [
        (Decimal("0"), 0, "0 kr"),
        (Decimal("999"), 0, "999 kr"),
        (Decimal("12345.6"), 0, f"12{THIN_SPACE}346 kr"),
        (Decimal("1234567.891"), 2, f"1{THIN_SPACE}234{THIN_SPACE}567,89 kr"),
        (Decimal("-50"), 0, f"{MINUS}50 kr"),
        (Decimal("0.5"), 0, "1 kr"),  # half up, not banker's rounding
        (Decimal("-0.4"), 0, "0 kr"),  # no negative zero
    ],
)
def test_format_nok(amount, decimals, expected):
    assert format_nok(amount, decimals=decimals) == expected


def test_percent_change():
    assert percent_change(Decimal(110), Decimal(100)) == Decimal(10)
    assert percent_change(Decimal(90), Decimal(-100)) == Decimal(190)
    assert percent_change(Decimal(5), Decimal(0)) is None
