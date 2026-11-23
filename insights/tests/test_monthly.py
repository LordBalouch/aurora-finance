from datetime import date

import pandas as pd
import pytest

from insights.monthly import (
    compare,
    complete_months,
    flow,
    monthly_summary,
    netted_totals,
    spending_by_group,
)


def frame(rows):
    """rows: (date, amount, category, group, kind)."""
    df = pd.DataFrame(rows, columns=["date", "amount", "category", "group", "kind"])
    df["date"] = pd.to_datetime(df["date"])
    return df


ROWS = [
    ("2026-01-05", 30000, "Salary", "Income", "income"),
    ("2026-01-10", -1000, "Groceries", "Food", "variable"),
    ("2026-01-11", 200, "Groceries", "Food", "variable"),  # refund
    ("2026-01-12", -5000, "Between own accounts", "Transfers", "transfer"),
    ("2026-01-13", 900, "Friends & family", "Money", "variable"),
    ("2026-01-14", -300, "Friends & family", "Money", "variable"),
    ("2026-03-05", 30000, "Salary", "Income", "income"),
    ("2026-03-06", -3000, "Rent & mortgage", "Housing", "fixed"),
    ("2026-03-07", -100, None, None, None),
]


def test_flow_classifies_refunds_transfers_and_netted():
    assert list(flow(frame(ROWS))) == [
        "income", "spending", "spending", "transfer", "netted", "netted",
        "income", "spending", "spending",
    ]  # fmt: skip


def test_summary_nets_refunds_and_fills_empty_months():
    s = monthly_summary(frame(ROWS))
    assert [str(m) for m in s.index] == ["2026-01", "2026-02", "2026-03"]
    jan, feb, mar = (s.iloc[i] for i in range(3))
    assert jan["spending"] == 800  # 1000 out, 200 back
    assert jan["income"] == 30000 and jan["net"] == 29200
    assert jan["netted"] == 600 and jan["transfer"] == -5000
    assert jan["count"] == 6
    assert feb["spending"] == 0 and pd.isna(feb["savings_rate"])
    assert mar["spending"] == 3100 and mar["savings_rate"] == pytest.approx(89.67)


def test_summary_of_nothing_is_empty():
    assert monthly_summary(frame([])).empty


def test_complete_months_drops_current_month_and_sparse_start():
    rows = [("2025-10-20", 50, "Refunds", "Income", "income")]
    for month in ("2025-11", "2025-12", "2026-01"):
        rows += [(f"{month}-{d:02d}", -10, "Groceries", "Food", "variable") for d in range(1, 21)]
    s = complete_months(monthly_summary(frame(rows)), date(2026, 1, 15))
    assert [str(m) for m in s.index] == ["2025-11", "2025-12"]


def test_compare_uses_previous_month_and_mean_of_months_before():
    c = compare(pd.Series([10.0, 20.0, float("nan"), 30.0, 50.0]))
    assert c == {"value": 50.0, "previous": 30.0, "average": 20.0}
    assert compare(pd.Series([5.0])) == {"value": 5.0, "previous": None, "average": None}


def test_spending_by_group_folds_tail_into_other_last():
    rows = [("2026-01-01", -(100 - i), f"c{i}", f"g{i}", "variable") for i in range(9)]
    rows.append(("2026-01-02", -500, "Misc", "Other", "variable"))
    groups = spending_by_group(frame(rows), top=3)
    assert list(groups.index) == ["g0", "g1", "g2", "Other"]
    assert groups["Other"] == 500 + sum(100 - i for i in range(3, 9))


def test_netted_totals_split_in_and_out():
    t = netted_totals(frame(ROWS)).loc["Friends & family"]
    assert (t["money_in"], t["money_out"], t["net"]) == (900, 300, 600)
