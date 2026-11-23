"""Monthly income, spending and net. Pure pandas, no Django.

Input is the frame from `ledger.frames.transactions_df`: one row per transaction with at least
`date` (datetime64), `amount` (float, negative = money out), `category`, `group` and `kind`.
"""

import pandas as pd

INCOME_KINDS = {"income"}
TRANSFER_KINDS = {"transfer"}
# Money both ways between people (gifts, shared bills, paying back): neither income nor
# spending. Reported as its own net line.
NETTED = {"Friends & family"}

FLOWS = ["income", "spending", "netted", "transfer"]


def flow(df: pd.DataFrame) -> pd.Series:
    """Classify each row as income, spending, netted or transfer.

    Spending categories keep money in (refunds) as spending, so a refund lowers spending
    instead of counting as income. Uncategorised rows go by sign.
    """
    kind = df["kind"]
    out = pd.Series("spending", index=df.index)
    out[kind.isna() & (df["amount"] > 0)] = "income"
    out[kind.isin(INCOME_KINDS)] = "income"
    out[kind.isin(TRANSFER_KINDS)] = "transfer"
    out[df["category"].isin(NETTED)] = "netted"
    return out


def monthly_summary(df: pd.DataFrame) -> pd.DataFrame:
    """One row per calendar month (no gaps): income, spending (positive = money spent),
    net, savings_rate (% of income, NaN without income), netted and transfer (net in),
    and count (number of transactions)."""
    columns = [*FLOWS, "net", "savings_rate", "count"]
    if df.empty:
        return pd.DataFrame(columns=columns, index=pd.PeriodIndex([], freq="M"), dtype=float)
    months = df["date"].dt.to_period("M")
    table = df.assign(flow=flow(df), month=months, amount=df["amount"].astype(float)).pivot_table(
        index="month", columns="flow", values="amount", aggfunc="sum", fill_value=0.0
    )
    every = pd.period_range(months.min(), months.max(), freq="M")
    table = table.reindex(index=every, columns=FLOWS, fill_value=0.0).astype(float)
    table["spending"] = -table["spending"] + 0.0  # + 0.0 turns -0.0 into 0.0
    table["net"] = table["income"] - table["spending"]
    table["savings_rate"] = table["net"] / table["income"].where(table["income"] > 0) * 100
    table["count"] = months.value_counts().reindex(every, fill_value=0).astype(float)
    return table[columns].round(2)


def complete_months(summary: pd.DataFrame, today, min_share: float = 0.2) -> pd.DataFrame:
    """Months that can be compared fairly.

    Drops the current calendar month and later (a half month would read as a drop), and
    leading months with fewer than `min_share` of the median month's transactions: late
    refunds keep their purchase date, which can fall before the first statement.
    """
    summary = summary[summary.index < pd.Period(today, freq="M")]
    if summary.empty:
        return summary
    full = summary["count"] >= summary["count"].median() * min_share
    return summary[full.cummax()]


def compare(series: pd.Series, window: int = 12) -> dict:
    """Latest value vs. the month before and vs. the mean of up to `window` months before it.
    Missing values (NaN) are None."""

    def clean(value):
        return None if value is None or pd.isna(value) else float(value)

    if series.empty:
        return {"value": None, "previous": None, "average": None}
    before = series.iloc[:-1].tail(window).dropna()
    return {
        "value": clean(series.iloc[-1]),
        "previous": clean(series.iloc[-2]) if len(series) > 1 else None,
        "average": clean(before.mean()) if len(before) else None,
    }


def spending_by_group(df: pd.DataFrame, top: int = 7) -> pd.Series:
    """Net spending per category group, largest first; the rest folded into a last 'Other'.
    Groups with net money in (more refunds than spending) are left out."""
    spend = df[flow(df) == "spending"]
    if spend.empty:
        return pd.Series(dtype=float)
    groups = spend["group"].fillna("Uncategorized")
    totals = -spend["amount"].groupby(groups).sum()
    totals = totals[totals > 0].sort_values(ascending=False)
    rest = totals.drop("Other", errors="ignore")
    head = rest.head(top)
    other = totals.get("Other", 0.0) + rest.iloc[top:].sum()
    if other > 0:
        head["Other"] = other
    return head.round(2)


def netted_totals(df: pd.DataFrame) -> pd.DataFrame:
    """Money in, money out and net per netted category (e.g. Friends & family)."""
    rows = df[flow(df) == "netted"]
    amount = rows["amount"]
    table = pd.DataFrame(
        {
            "money_in": amount.clip(lower=0),
            "money_out": -amount.clip(upper=0),
            "net": amount,
            "category": rows["category"],
        }
    )
    return table.groupby("category")[["money_in", "money_out", "net"]].sum().round(2)
