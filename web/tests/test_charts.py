from decimal import Decimal

import pytest

from web.charts import CATEGORICAL, chart


def test_spec_converts_decimal_and_keeps_order():
    spec = chart("line", ["Jan", "Feb"], {"Income": [Decimal("1.5"), Decimal(2)], "Spend": [1, 2]})
    assert spec["series"][0] == {"name": "Income", "data": [1.5, 2.0]}
    assert [s["name"] for s in spec["series"]] == ["Income", "Spend"]
    assert spec["palette"] == CATEGORICAL


def test_horizontal_only_for_bars():
    assert chart("bar", ["a"], {"s": [1]}, horizontal=True)["horizontal"] is True
    assert chart("line", ["a"], {"s": [1]}, horizontal=True)["horizontal"] is False


@pytest.mark.parametrize(
    "kwargs",
    [
        {"kind": "pie", "x": ["a"], "series": {"s": [1]}},
        {"kind": "line", "x": ["a", "b"], "series": {"s": [1]}},
        {"kind": "line", "x": ["a"], "series": {str(i): [i] for i in range(9)}},
    ],
)
def test_invalid_specs_raise(kwargs):
    with pytest.raises(ValueError):
        chart(**kwargs)
