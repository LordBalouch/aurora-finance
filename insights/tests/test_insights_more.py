from datetime import date

import pandas as pd
import pytest

from insights.anomalies import group_anomalies
from insights.counterparties import money_flow, top_merchants
from insights.forecast import month_forecast
from insights.patterns import by_day_of_month, weekday_by_month
from insights.recurring import find_recurring


def frame(rows):
    """rows: (date, amount, merchant, category, group, kind)."""
    cols = ["date", "amount", "merchant", "category", "group", "kind"]
    df = pd.DataFrame(rows, columns=cols)
    df["date"] = pd.to_datetime(df["date"])
    return df


def monthly(merchant, amount, day, months, cat="Subscriptions", group="Bills", kind="fixed"):
    return [(f"2026-{m:02d}-{day:02d}", amount, merchant, cat, group, kind) for m in months]


def test_recurring_finds_monthly_and_splits_two_loans_at_one_merchant():
    rows = monthly("netflix", -129, 5, range(1, 7))
    rows[-1] = ("2026-06-05", -149, "netflix", "Subscriptions", "Bills", "fixed")  # price up
    rows += monthly("bank", -3400, 1, range(1, 7), "Loans", "Debt")
    rows += monthly("bank", -5350, 21, range(1, 7), "Loans", "Debt")
    rows += [("2026-02-14", -500, "random shop", "Clothes", "Shopping", "variable")] * 3
    r = find_recurring(frame(rows)).set_index("name")
    assert set(r.index) == {"netflix", "bank (≈3 400)", "bank (≈5 350)"}
    assert r.loc["netflix", "cadence"] == "monthly" and r.loc["netflix", "price_change"] == 15.5
    assert r.loc["bank (≈5 350)", "next_expected"] == pd.Timestamp("2026-07-21")
    assert pd.isna(r.loc["bank (≈3 400)", "price_change"])
    assert r.index[0] == "bank (≈5 350)"  # largest monthly cost first


def test_recurring_ignores_irregular_and_income():
    rows = [(d, -100, "shop", "Groceries", "Food", "variable") for d in
            ("2026-01-01", "2026-01-03", "2026-02-20", "2026-02-22", "2026-05-01")]  # fmt: skip
    rows += monthly("employer", 30000, 25, range(1, 7), "Salary", "Income", "income")
    assert find_recurring(frame(rows)).empty


def test_group_anomalies_flags_a_spike_against_its_own_history():
    months = pd.period_range("2026-01", periods=8, freq="M")
    table = pd.DataFrame(
        {"Food": [5000, 5200, 4900, 5100, 5000, 5050, 4950, 9000], "Bills": [800] * 8},
        index=months,
    )
    a = group_anomalies(table)
    assert len(a) == 1
    row = a.iloc[0]
    assert (row["group"], row["month"], row["typical"]) == ("Food", months[-1], 5000)
    assert row["z"] > 3


def test_forecast_adds_due_recurring_and_typical_other_spending():
    rows = monthly("rent", -10000, 20, range(1, 8), "Rent", "Housing")
    for m, day in zip(range(1, 7), (2, 25, 5, 28, 3, 20), strict=True):  # irregular
        rows.append((f"2026-{m:02d}-{day:02d}", -3000, "shop", "Groceries", "Food", "variable"))
    rows.append(("2026-07-05", -1000, "shop", "Groceries", "Food", "variable"))
    df = frame(rows[:6] + rows[7:])  # July rent not paid yet
    from insights.recurring import find_recurring as fr

    f = month_forecast(df, fr(df), date(2026, 7, 15))
    assert f["spent"] == 1000 and f["recurring_left"] == 10000
    assert f["other_left"] == pytest.approx(3000 * 16 / 31, abs=0.01)
    assert f["typical"] == 13000
    assert month_forecast(df, fr(df), date(2026, 9, 1)) is None  # no data this month


def test_patterns_average_per_calendar_day():
    rows = [("2026-03-06", -100, "a", "Groceries", "Food", "variable"),  # Friday
            ("2026-03-13", -300, "a", "Groceries", "Food", "variable"),
            ("2026-03-02", -9999, "rent", "Rent", "Housing", "fixed")]  # fmt: skip
    months = pd.period_range("2026-03", periods=1, freq="M")
    table = weekday_by_month(frame(rows), months)
    assert table.loc["Fri", months[0]] == 100  # 400 over the 4 Fridays in March 2026
    assert table.loc["Mon", months[0]] == 0  # fixed costs are left out
    days = by_day_of_month(frame(rows), months)
    assert days[6] == 100 and days[31] == 0


def test_top_merchants_and_money_flow_balance():
    rows = [("2026-01-01", -600, "a", "Groceries", "Food", "variable"),
            ("2026-01-02", -400, "b", "Bus", "Transport", "variable"),
            ("2026-01-03", 700, "job", "Salary", "Income", "income"),
            ("2026-01-04", 200, "mum", "Friends & family", "Money", "variable")]  # fmt: skip
    top = top_merchants(frame(rows))
    assert list(top["merchant"]) == ["a", "b"] and top.loc[0, "share"] == 60
    sources, uses = money_flow(frame(rows))
    assert sources == {"Salary": 700, "Friends & family (net)": 200, "Shortfall": 100}
    assert sum(sources.values()) == sum(uses.values()) == 1000
