from datetime import date

import pandas as pd

from insights.budget import actual_vs_budget, burndown, goal_projection, progress, suggest
from insights.recurring import find_recurring


def frame(rows):
    """rows: (date, amount, merchant, group, kind)."""
    df = pd.DataFrame(rows, columns=["date", "amount", "merchant", "group", "kind"])
    df["date"] = pd.to_datetime(df["date"])
    df["category"] = df["group"]
    return df


def history():
    rows = []
    for m, food in zip(range(1, 7), (4000, 4200, 3900, 4100, 4050, 9000), strict=True):
        rows.append((f"2026-{m:02d}-10", -food, f"shop{m}", "Food", "variable"))
        rows.append((f"2026-{m:02d}-01", -8000, "rent", "Housing", "fixed"))
    rows.append(("2026-03-15", -1200, "dentist", "Health", "variable"))  # one-off
    return rows


def test_suggest_uses_median_and_ignores_one_offs():
    s = suggest(frame(history()), pd.Period("2026-07", freq="M"))
    assert s.to_dict() == {"Housing": 8000, "Food": 4100}  # median 4075 -> 4100; dentist 0


def test_progress_paces_and_forecasts():
    rows = history() + [("2026-07-05", -3000, "shop", "Food", "variable"),
                        ("2026-07-01", -8000, "rent", "Housing", "fixed")]  # fmt: skip
    df = frame(rows)
    p = progress(df, {"Food": 4000, "Housing": 8000}, pd.Period("2026-07"), date(2026, 7, 15),
                 recurring=find_recurring(df)).set_index("group")  # fmt: skip
    assert p.loc["Food", "expected"] == round(4000 * 15 / 31, 2)
    assert p.loc["Food", "status"] == "at risk"  # 3000 + typical 4075 × 16/31 > 4000
    # Rent is recurring and already paid this month: nothing more expected.
    assert p.loc["Housing", "status"] == "on track" and p.loc["Housing", "forecast"] == 8000
    past = progress(frame(rows), {"Food": 2000}, pd.Period("2026-06"), date(2026, 7, 15))
    assert past.iloc[0]["status"] == "over" and past.iloc[0]["forecast"] == 9000


def test_burndown_stops_at_today():
    rows = [
        ("2026-07-02", -100, "a", "Food", "variable"),
        ("2026-07-04", -50, "a", "Food", "variable"),
    ]
    b = burndown(frame(rows), pd.Period("2026-07"), ["Food"], date(2026, 7, 4))
    assert b["spent"].tolist()[:4] == [0, 100, 100, 150] and pd.isna(b["spent"].iloc[4])
    assert len(b) == 31


def test_actual_vs_budget_percent():
    budgets = pd.DataFrame({"month": [pd.Period("2026-06")], "group": ["Food"], "amount": [4500.0]})
    t = actual_vs_budget(frame(history()), budgets)
    assert t.loc["Food", pd.Period("2026-06")] == 200


def test_goal_projection():
    g = goal_projection(10000, 4000, 1000, date(2026, 1, 15))
    assert g["months"] == 6 and g["date"] == pd.Timestamp("2026-07-15") and g["share"] == 40
    assert goal_projection(10000, 4000, 0, date(2026, 1, 1))["months"] is None
    assert goal_projection(100, 150, 10, date(2026, 1, 1))["months"] == 0
