"""What the AI sees for each card: the same numbers the page shows, computed again here.

Each builder returns (title, task, facts). Facts are rounded to whole kroner and use plain
names so the prompt is short and readable in "What the AI saw".
"""

from datetime import date

import pandas as pd

from insights.anomalies import group_anomalies
from insights.budget import progress
from insights.counterparties import money_flow
from insights.debt import loan_payments, plan, years_table
from insights.forecast import month_forecast
from insights.monthly import (
    compare,
    complete_months,
    monthly_summary,
    netted_totals,
    spending_by_group,
)
from insights.recurring import find_recurring
from insights.trends import fixed_and_variable, group_overview, monthly_by_group
from ledger.frames import transactions_df
from ledger.models import Budget, TaxYear

TIPS = "Give a short summary and 2–3 concrete tips."


def _r(value):
    return None if value is None or pd.isna(value) else round(float(value))


def _base():
    df = transactions_df()
    summary = complete_months(monthly_summary(df), date.today())
    return df, summary


def _last12(df, summary):
    months = summary.tail(12).index
    window = df[(df["date"] >= months[0].start_time) & (df["date"] <= months[-1].end_time)]
    return months, window


def _kpis(summary):
    out = {}
    for col in ("income", "spending", "net"):
        c = compare(summary[col])
        out[col] = {
            "latest_month": _r(c["value"]),
            "month_before": _r(c["previous"]),
            "average_12_months_before": _r(c["average"]),
        }
    return out


def overview(params):
    df, summary = _base()
    months, window = _last12(df, summary)
    recurring = find_recurring(df)
    active = recurring[recurring["active"]]
    netted = netted_totals(window)
    return (
        "Overview",
        TIPS,
        {
            "latest_complete_month": months[-1].strftime("%B %Y"),
            "period": f"{months[0]} to {months[-1]}",
            "key_figures": _kpis(summary),
            "monthly_net_last_12": {str(m): _r(v) for m, v in summary["net"].tail(12).items()},
            "spending_by_group_12_months": {k: _r(v) for k, v in spending_by_group(window).items()},
            "friends_and_family_net_in": {k: _r(v) for k, v in netted["net"].items()},
            "recurring_payments_per_month": _r(active["monthly_cost"].sum()),
        },
    )


def month_story(params):
    df, summary = _base()
    month = summary.index[-1]
    table = monthly_by_group(df, summary.index, top=50)
    this = table.iloc[-1]
    usual = table.iloc[:-1].tail(12).median()
    anomalies = group_anomalies(table, last=1)
    forecast = month_forecast(df, find_recurring(df), date.today())
    task = (
        f"Tell the story of {month.strftime('%B %Y')} in 3–4 plain sentences as the summary: "
        "what happened, what stood out against a usual month and why it matters. "
        "Then 2 tips for next month."
    )
    return (
        f"The story of {month.strftime('%B %Y')}",
        task,
        {
            "month": month.strftime("%B %Y"),
            "key_figures": _kpis(summary),
            "groups_this_month_vs_usual": {
                g: {"this_month": _r(this[g]), "usual_month": _r(usual[g])}
                for g in table.columns
                if this[g] or usual[g]
            },
            "unusual": [
                {"group": a["group"], "amount": _r(a["amount"]), "usual": _r(a["typical"])}
                for _, a in anomalies.iterrows()
            ],
            "current_month_forecast": {k: _r(v) for k, v in forecast.items() if k != "due"}
            if forecast
            else "no data for the current month yet",
        },
    )


def trends(params):
    df, summary = _base()
    months, window = _last12(df, summary)
    groups = monthly_by_group(df, months)
    overview_ = group_overview(groups)
    split = fixed_and_variable(df, months)
    return (
        "Trends per group",
        TIPS,
        {
            "period": f"{months[0]} to {months[-1]}",
            "groups": {
                g: {
                    "total": _r(r["total"]),
                    "per_month": _r(r["average"]),
                    "change_last_3_vs_3_before_percent": _r(r["change"]),
                }
                for g, r in overview_.iterrows()
            },
            "fixed_costs_share_percent": _r(split["Fixed"].sum() / split.to_numpy().sum() * 100),
        },
    )


def recurring(params):
    df, _ = _base()
    r = find_recurring(df)
    active = r[r["active"]]
    return (
        "Recurring payments",
        (
            "Point out which recurring payments are worth reviewing or cancelling and any price "
            "rises. 2–3 tips."
        ),
        {
            "total_per_month": _r(active["monthly_cost"].sum()),
            "payments": [
                {
                    "name": p["name"],
                    "category": p["category"],
                    "every": p["cadence"],
                    "per_month": _r(p["monthly_cost"]),
                    "last_price_change_percent": _r(p["price_change"]),
                }
                for _, p in active.iterrows()
            ],
        },
    )


def anomalies(params):
    df, summary = _base()
    a = group_anomalies(monthly_by_group(df, summary.index, top=50))
    return (
        "Unusual months",
        "Explain what may lie behind each unusual month and what to check. 2–3 tips.",
        {
            "unusual_months": [
                {
                    "month": str(x["month"]),
                    "group": x["group"],
                    "amount": _r(x["amount"]),
                    "usual": _r(x["typical"]),
                }
                for _, x in a.iterrows()
            ],
        },
    )


def money_flow_card(params):
    df, summary = _base()
    months, window = _last12(df, summary)
    sources, uses = money_flow(window)
    return (
        "Where the money went",
        TIPS,
        {
            "period": f"{months[0]} to {months[-1]}",
            "money_from": {k: _r(v) for k, v in sources.items()},
            "money_to": {k: _r(v) for k, v in uses.items()},
        },
    )


def debt(params):
    table = years_table(list(TaxYear.objects.values()))
    payments = loan_payments(transactions_df())
    facts = {"loan_payments_per_month_bank": {k: _r(v) for k, v in payments.items()}}
    if not table.empty:
        latest = table.iloc[-1]
        facts["tax_settlement"] = {
            str(y): {
                "debt_31_dec": _r(r["debt"]),
                "interest_paid": _r(r["interest_expense"]),
                "effective_rate_percent": round(float(r["effective_rate"]), 1)
                if pd.notna(r["effective_rate"])
                else None,
            }
            for y, r in table.iterrows()
        }
        loans = [
            {
                "name": "all",
                "balance": float(latest["debt"]),
                "rate": float(latest["effective_rate"]),
                "payment": float(payments.sum()),
            }
        ]
        base, extra = plan(loans), plan(loans, extra=3000)
        facts["payoff_estimate"] = {
            "months_at_current_pace": base["months"],
            "interest_until_then": _r(base["interest"]),
            "months_with_3000_extra": extra["months"],
            "interest_with_3000_extra": _r(extra["interest"]),
            "note": "All debt as one loan at the effective rate; balances per lender unknown.",
        }
    return (
        "Debt",
        (
            "Give a short summary of the debt situation and 2–3 concrete steps to pay less "
            "interest (for example which kind of loan to pay first or refinance)."
        ),
        facts,
    )


def years(params):
    table = years_table(list(TaxYear.objects.values()))
    keep = [
        "business_profit",
        "total_income",
        "interest_expense",
        "tax_assessed",
        "tax_prepaid",
        "settlement",
        "bank_deposits",
        "debt",
        "net_wealth",
        "effective_rate",
        "interest_share",
    ]
    return (
        "Years from the tax settlements",
        (
            "Compare the years: what changed and why it matters. Include advance tax "
            "(forskuddsskatt) if prepaid and assessed tax are far apart. 2–3 tips."
        ),
        {str(y): {k: _r(r[k]) for k in keep if k in r} for y, r in table.iterrows()},
    )


def budget_card(params):
    df = transactions_df()
    month = pd.Period(params.get("month") or df["date"].max().to_period("M"), freq="M")
    budgets = Budget.objects.filter(month=month.start_time.date()).select_related("category")
    plan_ = {b.category.name: float(b.amount) for b in budgets}
    if not plan_:
        return "Budget", TIPS, {"month": str(month), "budget": "none yet"}
    p = progress(df, plan_, month, date.today(), recurring=find_recurring(df))
    return (
        f"Budget {month.strftime('%B %Y')}",
        ("Say which groups need attention and how to stay within budget. 2–3 tips."),
        {
            "month": str(month),
            "groups": {
                r["group"]: {
                    "budget": _r(r["budget"]),
                    "spent": _r(r["spent"]),
                    "forecast": _r(r["forecast"]),
                    "status": r["status"],
                }
                for _, r in p.iterrows()
            },
        },
    )


CARDS = {
    "overview": overview,
    "month_story": month_story,
    "trends": trends,
    "recurring": recurring,
    "anomalies": anomalies,
    "money_flow": money_flow_card,
    "debt": debt,
    "years": years,
    "budget": budget_card,
}
