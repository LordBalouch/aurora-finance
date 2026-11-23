"""Fixed sample numbers for the empty-state preview. Clearly labelled as sample in the UI;
replaced by real data once something is imported, and by `make_demo_data` (phase 6)."""

import pandas as pd

INCOME = [52400, 51800, 51800, 52100, 51800, 53900, 78200, 51800, 51800, 52600, 51800, 52300]
SPENDING = [47100, 38900, 36400, 40200, 39800, 41500, 52800, 49600, 42100, 39700, 43800, 40900]
GROUPS = {
    "Housing": 14200,
    "Food": 10820,
    "Leisure": 4860,
    "Transport": 3910,
    "Bills": 1290,
    "Other": 5820,
}


def summary(today) -> pd.DataFrame:
    """Twelve sample months ending with the last complete month, shaped like
    `insights.monthly.monthly_summary`."""
    months = pd.period_range(end=pd.Period(today, freq="M") - 1, periods=len(INCOME), freq="M")
    df = pd.DataFrame({"income": INCOME, "spending": SPENDING}, index=months, dtype=float)
    df["netted"] = df["transfer"] = 0.0
    df["net"] = df["income"] - df["spending"]
    df["savings_rate"] = (df["net"] / df["income"] * 100).round(2)
    df["count"] = 100.0
    return df


def groups() -> pd.Series:
    return pd.Series(GROUPS, dtype=float)
