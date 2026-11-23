from datetime import date
from decimal import Decimal

import pandas as pd
from django.shortcuts import render

from insights.anomalies import group_anomalies
from insights.forecast import month_forecast
from insights.formatting import format_nok, percent_change
from insights.monthly import (
    compare,
    complete_months,
    monthly_summary,
    netted_totals,
    spending_by_group,
)
from insights.recurring import find_recurring
from insights.trends import monthly_by_group
from ledger.frames import transactions_df

from . import sample
from .charts import chart
from .links import group_ids, month_range, transactions_url

PERIODS = {"3m": ("3M", 3), "6m": ("6M", 6), "12m": ("12M", 12), "all": ("All", None)}


def dec(value, places="1"):
    return None if value is None else Decimal(str(value)).quantize(Decimal(places))


def values(series: pd.Series) -> list:
    # NaN is not valid JSON; ECharts draws null as a gap.
    return [None if pd.isna(v) else float(v) for v in series]


def label(month: pd.Period) -> str:
    return month.strftime("%b %y")


def _delta(current, previous, *, higher_is_good: bool, unit: str = "%"):
    """unit "%" = relative change; "pp" (rates) and "kr" (values that can be negative, where
    a relative change misleads) = plain difference."""
    if current is None or previous is None:
        return None
    change = percent_change(current, previous) if unit == "%" else current - previous
    if change is None:
        return None
    # Below what the template shows (0.0 % or 0 kr) counts as unchanged, not as a red "down".
    flat = abs(change) < (0.5 if unit == "kr" else 0.05)
    return {
        "value": abs(change),
        "unit": unit,
        "up": change > 0,
        "good": (change > 0) == higher_is_good,
        "flat": flat,
    }


def _kpi(summary, key, title, column, *, higher_is_good=True, money=True, unit="%"):
    c = compare(summary[column])
    places = "1" if money else "0.1"
    value, previous, average = (dec(c[k], places) for k in ("value", "previous", "average"))
    if column == "savings_rate":
        # A mean of monthly rates lets one bad month dominate; use average net / income.
        income, net = compare(summary["income"])["average"], compare(summary["net"])["average"]
        average = dec(net / income * 100, places) if income and income > 0 else None
    last12 = summary[column].tail(12)
    return {
        "key": key,
        "label": title,
        "value": value,
        "money": money,
        "average": average,
        "delta": _delta(value, previous, higher_is_good=higher_is_good, unit=unit),
        "spark": chart(
            "spark", [label(m) for m in last12.index], {title: values(last12)}, money=money
        ),
    }


def period_from(request) -> str:
    period = request.GET.get("period", "12m")
    return period if period in PERIODS else "12m"


def period_links(period: str) -> list:
    return [(key, name, key == period) for key, (name, _) in PERIODS.items()]


def dashboard(request):
    period = period_from(request)
    today = date.today()
    df = transactions_df()
    summary = complete_months(monthly_summary(df), today)
    is_sample = summary.empty
    if is_sample:
        summary = sample.summary(today)

    months = PERIODS[period][1]
    window = summary.tail(months) if months else summary
    extra, group_links = {}, None
    if is_sample:
        groups, netted = sample.groups(), pd.DataFrame()
    else:
        start, end = window.index[0].start_time, window.index[-1].end_time
        in_window = df[(df["date"] >= start) & (df["date"] <= end)]
        groups, netted = spending_by_group(in_window), netted_totals(in_window)
        ids = group_ids(df)
        span_filter = {"from": start.date(), "to": end.date()}
        group_links = [[transactions_url(category=ids.get(g), **span_filter) if g in ids else None
                        for g in groups.index]]  # fmt: skip
        extra = _side_cards(df, summary, today)

    peak = window["spending"].idxmax()
    span = f"{label(window.index[0])} – {label(window.index[-1])}"
    top = groups.index[0] if len(groups) else None
    context = {
        "is_sample": is_sample,
        "periods": period_links(period),
        "latest_month": window.index[-1].strftime("%B %Y"),
        "span": span,
        "kpis": [
            _kpi(summary, "income", "Income", "income"),
            _kpi(summary, "spending", "Spending", "spending", higher_is_good=False),
            _kpi(summary, "net", "Net", "net", unit="kr"),
            _kpi(summary, "rate", "Savings rate", "savings_rate", money=False, unit="pp"),
        ],
        "trend": chart(
            "line",
            [label(m) for m in window.index],
            {"Income": values(window["income"]), "Spending": values(window["spending"])},
            area=True,
        ),
        "trend_insight": (
            f"Spending was highest in {peak.strftime('%B %Y')}: "
            f"{format_nok(dec(window.loc[peak, 'spending']))}."
        ),
        "categories": chart(
            "bar",
            list(groups.index),
            {"Spending": values(groups)},
            horizontal=True,
            links=group_links,
        ),
        "category_insight": (
            f"{top} is the largest group, {groups.iloc[0] / groups.sum():.0%} of spending."
            if top
            else "No spending in this period."
        ),
        "netted": [
            {
                "name": name,
                "money_in": dec(row["money_in"]),
                "money_out": dec(row["money_out"]),
                "net": dec(row["net"]),
            }
            for name, row in netted.iterrows()
        ],
        **extra,
    }
    return render(request, "web/dashboard.html", context)


def _side_cards(df, summary, today) -> dict:
    """This month's forecast, recurring payments and unusual months for the dashboard."""
    recurring = find_recurring(df)
    active = recurring[recurring["active"]]
    forecast = month_forecast(df, recurring, today)
    anomalies = group_anomalies(monthly_by_group(df, summary.index, top=50)).head(3)
    ids = group_ids(df)
    return {
        "data_until": df["date"].max().date(),
        "forecast": {k: dec(v) if isinstance(v, float) else v for k, v in forecast.items()}
        if forecast
        else None,
        "recurring_total": dec(active["monthly_cost"].sum()),
        "recurring_count": len(active),
        "price_rises": int((active["price_change"] > 0).sum()),
        "top_anomalies": [
            {
                "text": f"{a['group']} in {a['month'].strftime('%B')}",
                "amount": dec(a["amount"]),
                "typical": dec(a["typical"]),
                "url": transactions_url(category=ids.get(a["group"]), **month_range(a["month"])),
            }
            for _, a in anomalies.iterrows()
        ],
    }
