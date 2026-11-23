"""Budget suggestions, pacing and goals. Pure pandas, no Django.

Budgets are per category group (Food, Bills …) and count net spending, like the rest of the
analysis: a refund lowers what was spent.
"""

import calendar
import math

import pandas as pd

from .monthly import flow


def _group_spending(df: pd.DataFrame) -> pd.DataFrame:
    rows = df[flow(df) == "spending"]
    return rows.assign(
        month=rows["date"].dt.to_period("M"),
        spent=-rows["amount"],
        group=rows["group"].fillna("Uncategorized"),
    )


def suggest(df: pd.DataFrame, month: pd.Period, history: int = 6, step: int = 100) -> pd.Series:
    """Median monthly spending per group over the `history` months before `month`, rounded up
    to `step` kr. Months without spending in a group count as 0, so rare costs do not inflate
    the budget. Groups with no spending at all are left out."""
    rows = _group_spending(df)
    months = pd.period_range(end=month - 1, periods=history, freq="M")
    table = (
        rows[rows["month"].isin(months)]
        .pivot_table(index="month", columns="group", values="spent", aggfunc="sum", fill_value=0)
        .reindex(months, fill_value=0)
    )
    median = table.median()
    median = median[median > 0]
    return (
        median.apply(lambda v: math.ceil(v / step) * step)
        .astype(float)
        .sort_values(ascending=False)
    )


def progress(
    df: pd.DataFrame,
    budget: dict[str, float],
    month: pd.Period,
    today,
    recurring: pd.DataFrame | None = None,
    history: int = 6,
) -> pd.DataFrame:
    """One row per budgeted group: budget, spent, expected (budget × share of the month gone),
    forecast, remaining and status.

    forecast = spent + recurring payments in the group still due this month + the group's
    typical other spending (median of `history` months) for the rest of the month. A past
    month's forecast is what was spent. status: 'over' (spent > budget), 'at risk'
    (forecast > budget) or 'on track'.
    """
    today = pd.Timestamp(today)
    days = calendar.monthrange(month.year, month.month)[1]
    if today < month.start_time:
        elapsed = 0.0
    elif today > month.end_time:
        elapsed = 1.0
    else:
        elapsed = today.day / days
    rows = _group_spending(df)
    in_month = rows[(rows["month"] == month) & (rows["date"] <= today)]
    spent = in_month.groupby("group")["spent"].sum()

    due = pd.Series(dtype=float)
    recurring_merchants = set()
    if recurring is not None and len(recurring):
        active = recurring[recurring["active"]]
        recurring_merchants = set(active["merchant"])
        pending = active[
            (active["next_expected"] > today) & (active["next_expected"] <= month.end_time)
        ]
        due = pending.groupby(pending["group"].fillna("Uncategorized"))["amount"].sum()
    other = rows[~rows["merchant"].isin(recurring_merchants)]
    months = pd.period_range(end=month - 1, periods=history, freq="M")
    typical_other = (
        other[other["month"].isin(months)]
        .pivot_table(index="month", columns="group", values="spent", aggfunc="sum", fill_value=0)
        .reindex(months, fill_value=0)
        .median()
    )

    out = []
    for group, amount in budget.items():
        s = float(spent.get(group, 0.0))
        if elapsed >= 1:
            forecast = s
        else:
            forecast = (
                s
                + float(due.get(group, 0.0))
                + float(typical_other.get(group, 0.0)) * (1 - elapsed)
            )
        status = "over" if s > amount else "at risk" if forecast > amount else "on track"
        out.append(
            {
                "group": group,
                "budget": float(amount),
                "spent": round(s, 2),
                "expected": round(amount * elapsed, 2),
                "forecast": round(forecast, 2),
                "remaining": round(amount - s, 2),
                "status": status,
            }
        )
    columns = ["group", "budget", "spent", "expected", "forecast", "remaining", "status"]
    return pd.DataFrame(out, columns=columns)


def burndown(df: pd.DataFrame, month: pd.Period, groups: list[str], today) -> pd.DataFrame:
    """Cumulative spending in `groups` per day of `month` (NaN after `today`): columns day,
    spent."""
    today = pd.Timestamp(today)
    rows = _group_spending(df)
    rows = rows[(rows["month"] == month) & rows["group"].isin(groups)]
    days = pd.date_range(month.start_time, month.end_time.normalize(), freq="D")
    daily = rows.groupby(rows["date"].dt.normalize())["spent"].sum().reindex(days, fill_value=0)
    cumulative = daily.cumsum().where(days <= today)
    return pd.DataFrame({"day": days.day, "spent": cumulative.round(2).to_numpy()})


def actual_vs_budget(df: pd.DataFrame, budgets: pd.DataFrame) -> pd.DataFrame:
    """Spent as % of budget per (group, month). `budgets` has columns month (Period), group,
    amount. Returns rows = group, columns = month."""
    if budgets.empty:
        return pd.DataFrame()
    rows = _group_spending(df)
    spent = rows.groupby(["group", "month"])["spent"].sum()
    b = budgets.set_index(["group", "month"])["amount"]
    pct = (spent.reindex(b.index, fill_value=0) / b.where(b > 0) * 100).round(0)
    return pct.unstack("month").sort_index()


def goal_projection(target: float, saved: float, monthly: float, today) -> dict:
    """Months left and the projected date to reach `target` at `monthly` kr a month."""
    left = max(target - saved, 0.0)
    if left == 0:
        return {"left": 0.0, "months": 0, "date": pd.Timestamp(today).normalize(), "share": 100.0}
    share = round(saved / target * 100, 1) if target else 0.0
    if monthly <= 0:
        return {"left": left, "months": None, "date": None, "share": share}
    months = math.ceil(left / monthly)
    return {
        "left": left,
        "months": months,
        "date": (pd.Timestamp(today) + pd.DateOffset(months=months)).normalize(),
        "share": share,
    }
