"""Spending per category group over time. Pure pandas, no Django."""

import pandas as pd

from .monthly import flow


def _spending(df: pd.DataFrame) -> pd.DataFrame:
    spend = df[flow(df) == "spending"]
    return spend.assign(
        month=spend["date"].dt.to_period("M"),
        spent=-spend["amount"].astype(float),
        group=spend["group"].fillna("Uncategorized"),
    )


def monthly_by_group(df: pd.DataFrame, months: pd.PeriodIndex, top: int = 7) -> pd.DataFrame:
    """Net spending per month (rows, exactly `months`) and group (columns), largest group
    first; groups after `top` folded into a last 'Other' column."""
    spend = _spending(df)
    spend = spend[spend["month"].isin(months)]
    table = spend.pivot_table(
        index="month", columns="group", values="spent", aggfunc="sum", fill_value=0.0
    ).reindex(months, fill_value=0.0)
    order = table.sum().sort_values(ascending=False)
    order = order[order > 0].drop("Other", errors="ignore")
    keep, rest = list(order.index[:top]), [c for c in table.columns if c not in order.index[:top]]
    result = table[keep].copy()
    if rest and table[rest].to_numpy().sum() > 0:
        result["Other"] = table[rest].sum(axis=1)
    result.columns.name = None
    return result.round(2)


def fixed_and_variable(df: pd.DataFrame, months: pd.PeriodIndex) -> pd.DataFrame:
    """Net spending per month split by category kind: columns 'Fixed' and 'Variable'.
    Uncategorised spending counts as variable."""
    spend = _spending(df)
    spend = spend[spend["month"].isin(months)]
    kind = spend["kind"].map({"fixed": "Fixed"}).fillna("Variable")
    table = spend.assign(kind=kind).pivot_table(
        index="month", columns="kind", values="spent", aggfunc="sum", fill_value=0.0
    )
    return table.reindex(index=months, columns=["Fixed", "Variable"], fill_value=0.0).round(2)


def group_overview(table: pd.DataFrame, recent: int = 3) -> pd.DataFrame:
    """Per group (column of `monthly_by_group`): total, monthly average, and the change of
    the last `recent` months against the `recent` months before (percent, NaN without base)."""
    last = table.tail(recent).mean()
    before = table.iloc[-2 * recent : -recent].mean() if len(table) >= 2 * recent else None
    out = pd.DataFrame({"total": table.sum(), "average": table.mean()})
    if before is None:
        out["change"] = float("nan")
    else:
        out["change"] = (last - before) / before.where(before > 0) * 100
    return out.round(2)
