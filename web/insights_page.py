from datetime import date

import pandas as pd
from django.shortcuts import render

from insights.anomalies import group_anomalies
from insights.counterparties import money_flow, top_merchants
from insights.formatting import format_nok
from insights.monthly import complete_months, monthly_summary
from insights.patterns import by_day_of_month, weekday_by_month
from insights.recurring import find_recurring
from insights.trends import monthly_by_group
from ledger.frames import transactions_df

from .charts import chart, heatmap, sankey
from .links import group_ids, month_range, transactions_url
from .views import PERIODS, dec, label, period_from, period_links, values


def fold(values_by_name: dict, top: int = 7) -> dict:
    """Keep the `top` largest; the rest become one last 'Other' (fixed colour order, max 8)."""
    items = sorted(values_by_name.items(), key=lambda kv: -kv[1])
    kept = dict(items[:top])
    rest = sum(v for _, v in items[top:])
    if rest:
        kept["Other"] = kept.get("Other", 0) + rest
    return kept


def insights(request):
    period = period_from(request)
    df = transactions_df()
    summary = complete_months(monthly_summary(df), date.today())
    context = {"periods": period_links(period), "has_data": not summary.empty}
    if summary.empty:
        return render(request, "web/insights.html", context)

    count = PERIODS[period][1]
    months = (summary.tail(count) if count else summary).index
    start, end = months[0].start_time, months[-1].end_time
    window = df[(df["date"] >= start) & (df["date"] <= end)]
    ids = group_ids(df)
    span = f"{label(months[0])} – {label(months[-1])}"

    recurring = find_recurring(df)
    active = recurring[recurring["active"]]
    anomalies = group_anomalies(monthly_by_group(df, summary.index, top=50))
    heat = weekday_by_month(df, months)
    days = by_day_of_month(df, months)
    merchants = top_merchants(window)
    sources, uses = money_flow(window)

    context |= {
        "span": span,
        "recurring": [
            {
                "name": r["name"],
                "category": r["category"],
                "cadence": r["cadence"],
                "amount": dec(r["amount"]),
                "monthly": dec(r["monthly_cost"]),
                "next": r["next_expected"].date(),
                "price_change": dec(r["price_change"]) if pd.notna(r["price_change"]) else None,
                "url": transactions_url(merchant=r["merchant"]),
            }
            for _, r in active.iterrows()
        ],
        "recurring_total": dec(active["monthly_cost"].sum()),
        "price_rises": int((active["price_change"] > 0).sum()),
        "anomalies": [
            {
                "month": a["month"].strftime("%B %Y"),
                "group": a["group"],
                "amount": dec(a["amount"]),
                "typical": dec(a["typical"]),
                "difference": dec(a["difference"]),
                "up": a["difference"] > 0,
                "url": transactions_url(category=ids.get(a["group"]), **month_range(a["month"])),
            }
            for _, a in anomalies.iterrows()
        ],
        "heatmap": heatmap([label(m) for m in months], list(heat.index), heat.to_numpy().tolist()),
        "days": chart("bar", [str(d) for d in days.index], {"Per day": values(days)}),
        "busiest_weekday": heat.mean(axis=1).idxmax(),
        "merchants": [
            {
                "merchant": m["merchant"],
                "group": m["group"],
                "count": int(m["count"]),
                "total": dec(m["total"]),
                "average": dec(m["average"]),
                "share": dec(m["share"], "0.1"),
                "url": transactions_url(
                    merchant=m["merchant"], **{"from": start.date(), "to": end.date()}
                ),
            }
            for _, m in merchants.iterrows()
        ],
        "sankey": sankey(sources, fold(uses)),
        "flow_insight": _flow_insight(sources, uses),
    }
    return render(request, "web/insights.html", context)


FUNDING = ("Friends & family (net)", "From own accounts (net)", "Shortfall")


def _flow_insight(sources: dict, uses: dict) -> str:
    income = sum(v for k, v in sources.items() if k not in FUNDING)
    covered = {k: v for k, v in sources.items() if k in FUNDING}
    if not covered:
        left = format_nok(dec(uses.get("Left over", 0)))
        return f"Income covered all spending, with {left} left over."
    parts = [f"{k.replace(' (net)', '').lower()} {format_nok(dec(v))}" for k, v in covered.items()]
    gap = sum(covered.values())
    return (
        f"Spending was {format_nok(dec(gap))} more than income ({format_nok(dec(income))}). "
        f"Covered by: {', '.join(parts)}."
    )
