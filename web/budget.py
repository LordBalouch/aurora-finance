"""Monthly budget per category group, pacing, forecast, goals and the year view."""

from datetime import date
from decimal import Decimal, InvalidOperation

import pandas as pd
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from insights.budget import actual_vs_budget, burndown, goal_projection, progress, suggest
from insights.recurring import find_recurring
from ledger.frames import transactions_df
from ledger.models import Budget, Category, Goal

from .charts import chart, heatmap
from .forms import GoalForm
from .links import month_range, transactions_url
from .views import dec, label

# Diverging: under budget (blue) → on budget (neutral) → over budget (orange).
DIVERGING = ["#1d4f8f", "#3987e5", "#3a3f4b", "#d95926", "#f08a5d"]


def spending_groups():
    return Category.objects.filter(parent__isnull=True, kind__in=["fixed", "variable"])


def _month(value: str | None, df: pd.DataFrame, today: date) -> tuple[pd.Period, str | None]:
    """The month asked for, else this month, else the latest month with data (with a note)."""
    if value:
        try:
            return pd.Period(value, freq="M"), None
        except ValueError:
            pass
    current = pd.Period(today, freq="M")
    if df.empty or df["date"].max() >= current.start_time:
        return current, None
    latest = df["date"].max().to_period("M")
    note = f"No data for {current.strftime('%B')} yet: showing {latest.strftime('%B %Y')}."
    return latest, note


def budget(request):
    today = date.today()
    df = transactions_df()
    month, note = _month(request.GET.get("month"), df, today)
    groups = {c.name: c for c in spending_groups()}
    saved = {b.category.name: b for b in Budget.objects.filter(month=month.start_time.date())
             .select_related("category")}  # fmt: skip
    context = {
        "month": month,
        "month_label": month.strftime("%B %Y"),
        "prev": (month - 1).strftime("%Y-%m"),
        "next": (month + 1).strftime("%Y-%m"),
        "note": note,
        "has_budget": bool(saved),
        "has_previous": Budget.objects.filter(month=(month - 1).start_time.date()).exists(),
        "goals": _goals(today),
        "goal_form": GoalForm(),
    }
    if not df.empty:
        context["suggestion"] = {g: dec(v) for g, v in suggest(df, month).items() if g in groups}
    if saved:
        plan = {name: float(b.amount) for name, b in saved.items()}
        p = progress(df, plan, month, today, recurring=find_recurring(df)).set_index("group")
        rows = []
        for name in sorted(plan, key=lambda n: -plan[n]):
            r = p.loc[name]
            budget_amount = r["budget"] or 1
            rows.append(
                {
                    "group": name,
                    "pk": groups[name].pk if name in groups else None,
                    "budget": dec(r["budget"]),
                    "spent": dec(r["spent"]),
                    "forecast": dec(r["forecast"]),
                    "remaining": dec(r["remaining"]),
                    "status": r["status"],
                    "fill": min(r["spent"] / budget_amount * 100, 100),
                    "marker": min(r["expected"] / budget_amount * 100, 100),
                    "url": transactions_url(
                        category=groups[name].pk if name in groups else None, **month_range(month)
                    ),  # fmt: skip
                }
            )
        total = p["budget"].sum()
        days = burndown(df, month, list(plan), today)
        ideal = [round(total * d / len(days), 2) for d in days["day"]]
        context |= {
            "rows": rows,
            "total_budget": dec(total),
            "total_spent": dec(p["spent"].sum()),
            "total_forecast": dec(p["forecast"].sum()),
            "counts": p["status"].value_counts().to_dict(),
            "burndown": chart(
                "line",
                [str(d) for d in days["day"]],
                {
                    "Spent": [None if pd.isna(v) else float(v) for v in days["spent"]],
                    "Budget pace": ideal,
                },  # fmt: skip
            ),
        }
    context |= _year_view(df)
    return render(request, "web/budget.html", context)


def _year_view(df) -> dict:
    budgets = pd.DataFrame(
        [
            {
                "month": pd.Period(b.month, freq="M"),
                "group": b.category.name,
                "amount": float(b.amount),
            }
            for b in Budget.objects.select_related("category")
        ]  # fmt: skip
    )
    if budgets.empty or budgets["month"].nunique() < 2:
        return {}
    table = actual_vs_budget(df, budgets).fillna(0)
    months = list(table.columns)
    spec = heatmap([label(m) for m in months], list(table.index), table.to_numpy().tolist(),
                   money=False)  # fmt: skip
    spec |= {"palette": DIVERGING, "min": 0, "max": 200, "unit": "% of budget"}
    return {"year_view": spec}


def _goals(today):
    out = []
    for g in Goal.objects.all():
        p = goal_projection(float(g.target_amount), float(g.saved), float(g.monthly), today)
        late = bool(g.target_date and p["date"] and p["date"].date() > g.target_date)
        when = p["date"].date() if p["date"] is not None else None
        out.append(
            {"goal": g, "share": min(p["share"], 100), "months": p["months"], "date": when,
             "late": late}
        )  # fmt: skip
    return out


@require_POST
def budget_create(request):
    """Fill a month from history (suggestion) or from the month before."""
    month = pd.Period(request.POST["month"], freq="M")
    first = month.start_time.date()
    groups = {c.name: c for c in spending_groups()}
    if request.POST.get("source") == "previous":
        previous = Budget.objects.filter(month=(month - 1).start_time.date())
        amounts = {b.category.name: b.amount for b in previous.select_related("category")}
    else:
        amounts = {g: Decimal(str(v)) for g, v in suggest(transactions_df(), month).items()}
    for name, amount in amounts.items():
        if name in groups:
            Budget.objects.update_or_create(month=first, category=groups[name],
                                            defaults={"amount": amount})  # fmt: skip
    messages.success(request, f"Budget for {month.strftime('%B %Y')} created. Adjust as you like.")
    return redirect(f"/budget/?month={month.strftime('%Y-%m')}")


@require_POST
def budget_save(request):
    month = pd.Period(request.POST["month"], freq="M")
    first = month.start_time.date()
    for c in spending_groups():
        raw = request.POST.get(f"amount_{c.pk}", "").replace(" ", "").replace(",", ".")
        if raw == "":
            Budget.objects.filter(month=first, category=c).delete()
            continue
        try:
            amount = Decimal(raw)
        except InvalidOperation:
            messages.error(request, f"“{raw}” is not an amount ({c.name}).")
            continue
        Budget.objects.update_or_create(month=first, category=c, defaults={"amount": amount})
    messages.success(request, "Budget saved.")
    return redirect(f"/budget/?month={month.strftime('%Y-%m')}")


@require_POST
def goal_add(request):
    form = GoalForm(request.POST)
    if form.is_valid():
        form.save()
        messages.success(request, "Goal added.")
    else:
        messages.error(request, "Check the goal: " + "; ".join(
            f"{k}: {' '.join(v)}" for k, v in form.errors.items()))  # fmt: skip
    return redirect("/budget/#goals")


@require_POST
def goal_delete(request, pk):
    get_object_or_404(Goal, pk=pk).delete()
    messages.success(request, "Goal removed.")
    return redirect("/budget/#goals")
