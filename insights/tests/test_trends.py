import pandas as pd

from insights.trends import fixed_and_variable, group_overview, monthly_by_group

from .test_monthly import frame

MONTHS = pd.period_range("2026-01", "2026-03", freq="M")
ROWS = [
    ("2026-01-02", -1000, "Rent", "Housing", "fixed"),
    ("2026-01-03", -300, "Groceries", "Food", "variable"),
    ("2026-01-04", 100, "Groceries", "Food", "variable"),  # refund
    ("2026-03-02", -1000, "Rent", "Housing", "fixed"),
    ("2026-03-03", -50, "Misc", "Other", "variable"),
    ("2026-03-04", -40, "Bus", "Transport", "variable"),
    ("2026-03-05", 5000, "Salary", "Income", "income"),
    ("2025-12-05", -999, "Rent", "Housing", "fixed"),  # outside the months
]


def test_monthly_by_group_fills_months_and_folds_other_last():
    t = monthly_by_group(frame(ROWS), MONTHS, top=2)
    assert list(t.columns) == ["Housing", "Food", "Other"]
    assert list(t.index) == list(MONTHS)
    assert t.loc[pd.Period("2026-01"), "Food"] == 200
    assert t.loc[pd.Period("2026-02")].sum() == 0
    assert t.loc[pd.Period("2026-03"), "Other"] == 90  # Misc 50 + Transport 40


def test_fixed_and_variable():
    t = fixed_and_variable(frame(ROWS), MONTHS)
    assert t.loc[pd.Period("2026-01")].tolist() == [1000, 200]
    assert t.loc[pd.Period("2026-02")].tolist() == [0, 0]


def test_group_overview_compares_last_months_with_months_before():
    table = pd.DataFrame(
        {"Food": [100, 100, 200, 200]}, index=pd.period_range("2026-01", periods=4, freq="M")
    )
    o = group_overview(table, recent=2).loc["Food"]
    assert (o["total"], o["average"], o["change"]) == (600, 150, 100)
    assert pd.isna(group_overview(table, recent=3).loc["Food", "change"])
