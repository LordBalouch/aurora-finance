"""Year figures (tax settlements) and debt."""

import pandas as pd
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from insights.debt import loan_payments, plan, years_table
from ledger.frames import transactions_df
from ledger.models import DebtBalance, TaxYear

from .charts import chart
from .forms import DebtBalanceForm, TaxYearForm
from .views import dec

# (field, label, higher_is_good) — the rows of the year comparison.
YEAR_ROWS = [
    ("business_profit", "Business profit", True),
    ("wages", "Wages", True),
    ("benefits", "Benefits", True),
    ("total_income", "Total income", True),
    ("interest_expense", "Interest paid", False),
    ("total_deductions", "Deductions", None),
    ("tax_assessed", "Tax assessed", False),
    ("tax_prepaid", "Tax prepaid", None),
    ("settlement", "Refund (+) / owed (−)", True),
    ("bank_deposits", "Bank deposits", True),
    ("vehicles", "Vehicles", None),
    ("business_assets", "Business assets", None),
    ("gross_wealth", "Gross wealth", True),
    ("debt", "Debt", False),
    ("net_wealth", "Net wealth", True),
]
RATE_ROWS = [
    ("effective_rate", "Effective interest rate", False),
    ("interest_share", "Interest as % of income", False),
    ("tax_rate", "Tax as % of income", False),
]


def _change(new, old, higher_is_good):
    if pd.isna(new) or pd.isna(old) or new == old:
        return None
    up = new > old
    return {"up": up, "good": None if higher_is_good is None else up == higher_is_good}


def years(request):
    table = years_table(list(TaxYear.objects.values()))
    context = {"has_data": not table.empty}
    if table.empty:
        return render(request, "web/years.html", context)
    year_list = list(table.index)
    rows = []
    for field, label, good in YEAR_ROWS + RATE_ROWS:
        col = table[field] if field in table else pd.Series(index=table.index, dtype=float)
        if col.isna().all():
            continue
        is_rate = field in {f for f, _, _ in RATE_ROWS}
        cells = [dec(v, "0.1" if is_rate else "1") if pd.notna(v) else None for v in col]
        rows.append(
            {
                "label": label,
                "rate": is_rate,
                "cells": cells,
                "change": _change(col.iloc[-1], col.iloc[-2], good) if len(col) > 1 else None,
            }
        )
    x = [str(y) for y in year_list]
    latest, first = table.iloc[-1], table.iloc[0]
    context |= {
        "years": year_list,
        "rows": rows,
        "income_chart": chart(
            "bar",
            x,
            {
                "Income": list(table["total_income"].fillna(0)),
                "Interest paid": list(table["interest_expense"].fillna(0)),
                "Tax assessed": list(table["tax_assessed"].fillna(0)),
            },
        ),
        "wealth_chart": chart(
            "bar",
            x,
            {
                "Gross wealth": list(table["gross_wealth"].fillna(0)),
                "Debt": list(table["debt"].fillna(0)),
                "Net wealth": list(table["net_wealth"].fillna(0)),
            },
        ),
        "insight": _years_insight(table, first, latest),
        "notes": [(y.year, y.notes) for y in TaxYear.objects.exclude(notes="")],
    }
    return render(request, "web/years.html", context)


def _years_insight(table, first, latest) -> str:
    if len(table) < 2:
        return f"{int(latest.name)}: net wealth {dec(latest['net_wealth'])} kr."
    parts = []
    if pd.notna(latest.get("interest_expense")) and pd.notna(first.get("interest_expense")):
        parts.append(
            f"interest paid went from {dec(first['interest_expense']):,} to "
            f"{dec(latest['interest_expense']):,} kr".replace(",", " ")
        )
    if pd.notna(latest.get("net_wealth_change")):
        word = "fell" if latest["net_wealth_change"] < 0 else "grew"
        parts.append(
            f"net wealth {word} by {abs(dec(latest['net_wealth_change'])):,} kr".replace(",", " ")
        )
    return f"From {int(first.name)} to {int(latest.name)}: " + "; ".join(parts) + "."


def year_edit(request, year=None):
    instance = get_object_or_404(TaxYear, year=year) if year else None
    form = TaxYearForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        saved = form.save()
        messages.success(request, f"Saved {saved.year}.")
        return redirect("web:years")
    return render(request, "web/year_form.html", {"form": form, "instance": instance})


def _loans(balances, payments: pd.Series, default_rate: float | None) -> tuple[list, bool]:
    """Loans for the payoff plan: per lender when balances per lender exist, else one loan
    with the latest total (tax settlement) and all loan payments in the bank data."""
    per_lender = [b for b in balances if b.source != DebtBalance.Source.TAX]
    if per_lender:
        loans = []
        for b in per_lender:
            payment = b.monthly_payment or payments.get(b.merchant, 0)
            known = b.annual_rate is not None
            loans.append(
                {
                    "name": b.lender,
                    "balance": float(b.balance),
                    "rate": float(b.annual_rate) if known else (default_rate or 0),
                    "payment": float(payment),
                    "estimated_rate": not known,
                }
            )
        return loans, False
    total = next((b for b in balances if b.source == DebtBalance.Source.TAX), None)
    if total is None:
        return [], False
    return [{"name": "All loans", "balance": float(total.balance), "rate": default_rate or 0,
             "payment": float(payments.sum()), "estimated_rate": True}], True  # fmt: skip


def debt(request):
    try:
        extra = max(0, min(int(request.GET.get("extra", "0") or 0), 1_000_000))
    except ValueError:
        extra = 0
    table = years_table(list(TaxYear.objects.values()))
    rate = float(table["effective_rate"].iloc[-1]) if not table.empty else None
    payments = loan_payments(transactions_df())
    # Latest balance per lender.
    latest = {}
    for b in DebtBalance.objects.order_by("lender", "-as_of"):
        latest.setdefault(b.lender, b)
    loans, aggregate = _loans(list(latest.values()), payments, rate)
    base = plan(loans) if loans else None
    faster = plan(loans, extra=extra) if loans and extra else None
    context = {
        "extra": extra,
        "rate": dec(rate, "0.1") if rate is not None else None,
        "interest_year": dec(table["interest_expense"].iloc[-1]) if not table.empty else None,
        "tax_year": int(table.index[-1]) if not table.empty else None,
        "payments": [{"merchant": m, "monthly": dec(v)} for m, v in payments.items()],
        "payments_total": dec(payments.sum()),
        "balances": list(latest.values()),
        "loans": loans,
        "debt_total": dec(sum(loan["balance"] for loan in loans)) if loans else None,
        "debt_as_of": max((b.as_of for b in latest.values()), default=None),
        "aggregate": aggregate,
        "base": base,
        "faster": faster,
        "form": DebtBalanceForm(),
    }
    if base and base["months"]:
        n = len(faster["balances"]) if faster and faster["months"] else 0
        months = max(len(base["balances"]), n)
        x = [f"{m // 12}y {m % 12}m" if m % 12 else f"{m // 12}y" for m in range(months)]
        series = {"Current pace": base["balances"] + [0] * (months - len(base["balances"]))}
        if n:
            series[f"+{extra} kr/month"] = faster["balances"] + [0] * (months - n)
        context["chart"] = chart("line", x, series, area=False)
        if faster and faster["months"]:
            context["saved_months"] = base["months"] - faster["months"]
            context["saved_interest"] = dec(base["interest"] - faster["interest"])
    if request.headers.get("HX-Request"):
        return render(request, "web/_debt_plan.html", context)
    return render(request, "web/debt.html", context)


def debt_add(request):
    form = DebtBalanceForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Balance saved.")
        return redirect("web:debt")
    return render(request, "web/debt_form.html", {"form": form})


def debt_delete(request, pk):
    if request.method == "POST":
        get_object_or_404(DebtBalance, pk=pk).delete()
        messages.success(request, "Balance removed.")
    return redirect("web:debt")
