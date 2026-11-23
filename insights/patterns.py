"""When money is spent: weekday and day-of-month patterns. Pure pandas, no Django.

Only variable spending counts: fixed bills fall on set dates and would hide the pattern.
"""

import pandas as pd

from .monthly import flow

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _variable(df: pd.DataFrame) -> pd.DataFrame:
    rows = df[(flow(df) == "spending") & (df["kind"].fillna("variable") == "variable")]
    return rows.assign(spent=-rows["amount"])


def weekday_by_month(df: pd.DataFrame, months: pd.PeriodIndex) -> pd.DataFrame:
    """Average variable spending per calendar day: rows = weekday (Mon..Sun), columns = month.
    Each cell divides by how many of that weekday the month has, so 5-Friday months are fair."""
    rows = _variable(df)
    rows = rows[rows["date"].dt.to_period("M").isin(months)]
    totals = rows.groupby([rows["date"].dt.day_of_week, rows["date"].dt.to_period("M")])[
        "spent"
    ].sum()
    days = pd.Series(pd.date_range(months[0].start_time, months[-1].end_time.normalize()))
    count = days.groupby([days.dt.day_of_week, days.dt.to_period("M")]).size()
    table = (totals.reindex(count.index, fill_value=0.0) / count).unstack(fill_value=0.0)
    table = table.reindex(index=range(7), columns=months, fill_value=0.0)
    table.index = WEEKDAYS
    return table.round(2)


def by_day_of_month(df: pd.DataFrame, months: pd.PeriodIndex) -> pd.Series:
    """Average variable spending on each day of the month (1..31) across `months`; a day only
    counts in months that have it."""
    rows = _variable(df)
    rows = rows[rows["date"].dt.to_period("M").isin(months)]
    totals = rows.groupby(rows["date"].dt.day)["spent"].sum()
    present = pd.Series([m.days_in_month for m in months])
    months_with_day = pd.Series({d: int((present >= d).sum()) for d in range(1, 32)})
    return (totals.reindex(range(1, 32), fill_value=0.0) / months_with_day).round(2)
