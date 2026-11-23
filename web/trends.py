from datetime import date

import pandas as pd
from django.shortcuts import render

from insights.monthly import complete_months, monthly_summary
from insights.trends import fixed_and_variable, group_overview, monthly_by_group
from ledger.frames import transactions_df

from .charts import chart
from .links import group_ids, month_range, transactions_url
from .views import PERIODS, dec, label, period_from, period_links, values


def trends(request):
    period = period_from(request)
    df = transactions_df()
    summary = complete_months(monthly_summary(df), date.today())
    context = {"periods": period_links(period), "has_data": not summary.empty}
    if summary.empty:
        return render(request, "web/trends.html", context)

    count = PERIODS[period][1]
    months = (summary.tail(count) if count else summary).index
    x = [label(m) for m in months]
    groups = monthly_by_group(df, months)
    ids = group_ids(df)
    split = fixed_and_variable(df, months)
    overview = group_overview(groups)
    shared_max = float(groups.to_numpy().max()) if groups.size else None

    fixed_share = split["Fixed"].sum() / split.to_numpy().sum() if split.to_numpy().sum() else 0
    biggest_rise = overview["change"].dropna().sort_values()
    rise = biggest_rise.index[-1] if len(biggest_rise) and biggest_rise.iloc[-1] > 0 else None
    context |= {
        "span": f"{x[0]} – {x[-1]}",
        "stacked": chart(
            "bar",
            x,
            {g: values(groups[g]) for g in groups.columns},
            stack=True,
            links=[
                [
                    transactions_url(category=ids[g], **month_range(m)) if g in ids else None
                    for m in months
                ]
                for g in groups.columns
            ],  # fmt: skip
        ),
        "split": chart("bar", x, {k: values(split[k]) for k in split.columns}, stack=True),
        "fixed_insight": f"Fixed costs are {fixed_share:.0%} of spending in the period.",
        "stack_insight": (
            f"{rise} rose the most: {overview.loc[rise, 'change']:+.0f} % in the last 3 months "
            "against the 3 before."
            if rise
            else "No group rose over the last 3 months."
        ),
        "multiples": [
            {
                "key": f"group-{i}",
                "name": g,
                "total": dec(overview.loc[g, "total"]),
                "average": dec(overview.loc[g, "average"]),
                "change": dec(overview.loc[g, "change"])
                if pd.notna(overview.loc[g, "change"])
                else None,
                "spark": chart("spark", x, {g: values(groups[g])}, y_max=shared_max),
            }
            for i, g in enumerate(groups.columns)
        ],
    }
    return render(request, "web/trends.html", context)
