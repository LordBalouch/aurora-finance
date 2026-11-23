"""Month-end forecast. Pure pandas, no Django."""

import calendar

import pandas as pd

from .monthly import flow


def month_forecast(
    df: pd.DataFrame, recurring: pd.DataFrame, today, *, history: int = 6
) -> dict | None:
    """Expected spending for the month `today` is in.

    forecast = spent so far + recurring payments still due this month + typical other
    spending for the remaining days. 'Typical other' is the median over the last `history`
    complete months of spending that is not from recurring merchants, scaled to the days left.
    Returns None when the data does not reach into this month (nothing to forecast from).
    """
    today = pd.Timestamp(today)
    start = today.replace(day=1)
    days = calendar.monthrange(today.year, today.month)[1]
    end = start + pd.Timedelta(days=days - 1)
    if df.empty or df["date"].max() < start:
        return None
    spend = df[flow(df) == "spending"].assign(month=lambda d: d["date"].dt.to_period("M"))
    so_far = -spend.loc[(spend["date"] >= start) & (spend["date"] <= today), "amount"].sum()

    active = recurring[recurring["active"]] if len(recurring) else recurring
    due = active[(active["next_expected"] > today) & (active["next_expected"] <= end)]
    recurring_left = float(due["amount"].sum()) if len(due) else 0.0

    merchants = set(active["merchant"]) if len(active) else set()
    other = spend[~spend["merchant"].isin(merchants)]
    current = pd.Period(today, freq="M")
    monthly_other = -other[other["month"] < current].groupby("month")["amount"].sum()
    monthly_total = -spend[spend["month"] < current].groupby("month")["amount"].sum()
    typical_other = monthly_other.tail(history).median() if len(monthly_other) else 0.0
    days_left = (end - today).days
    other_left = typical_other * days_left / days

    forecast = so_far + recurring_left + other_left
    typical = monthly_total.tail(history).median() if len(monthly_total) else None
    return {
        "spent": round(float(so_far), 2),
        "recurring_left": round(recurring_left, 2),
        "other_left": round(float(other_left), 2),
        "forecast": round(float(forecast), 2),
        "typical": round(float(typical), 2) if typical is not None else None,
        "days_left": days_left,
        "due": due[["name", "amount", "next_expected"]].to_dict("records") if len(due) else [],
    }
