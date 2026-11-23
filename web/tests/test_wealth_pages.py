from datetime import date

import pytest
from django.urls import reverse

from ledger.models import Account, Category, DebtBalance, TaxYear

pytestmark = pytest.mark.django_db


def make_years():
    for year, debt, interest, net in (
        (2024, 1000000, 50000, 900000),
        (2025, 1200000, 110000, 500000),
    ):
        TaxYear.objects.create(year=year, total_income=500000, business_profit=400000,
                               interest_expense=interest, tax_assessed=100000, debt=debt,
                               gross_wealth=debt + net, net_wealth=net)  # fmt: skip


def test_years_empty_and_with_data(client):
    assert not client.get(reverse("web:years")).context["has_data"]
    make_years()
    ctx = client.get(reverse("web:years")).context
    rows = {r["label"]: r for r in ctx["rows"]}
    assert rows["Debt"]["change"] == {"up": True, "good": False}
    assert rows["Effective interest rate"]["cells"][-1] == 10  # 110 000 / 1.1 m
    assert rows["Effective interest rate"]["cells"][0] == 5  # one decimal kept, not rounded
    assert "net wealth fell by 400 000 kr" in ctx["insight"]


def test_year_form_saves(client):
    response = client.post(reverse("web:year_new"), {"year": 2023, "debt": "100", "notes": ""})
    assert response.status_code == 302 and TaxYear.objects.get(year=2023).debt == 100


def test_debt_plan_uses_total_and_bank_payments(client, add_transactions):
    make_years()
    DebtBalance.objects.create(lender="All loans (tax settlement)", as_of=date(2025, 12, 31),
                               balance=1200000, source="tax")  # fmt: skip
    acc = Account.objects.create(name="Everyday")
    debt = Category.objects.create(name="Debt", kind="fixed")
    loans = Category.objects.create(name="Loans & credit", parent=debt, kind="fixed")
    add_transactions(acc, [(date(2026, m, 1), "-20000", loans) for m in range(1, 13)])
    ctx = client.get(reverse("web:debt")).context
    assert ctx["aggregate"] and ctx["payments_total"] == 20000
    assert ctx["base"]["months"] > 60
    faster = client.get(reverse("web:debt") + "?extra=5000").context
    assert faster["saved_months"] > 0 and faster["saved_interest"] > 0
    partial = client.get(reverse("web:debt") + "?extra=5000", HTTP_HX_REQUEST="true")
    assert b'id="debt-plan"' in partial.content and b"<html" not in partial.content


def test_debt_per_lender_when_balances_exist(client):
    DebtBalance.objects.create(lender="Card", as_of=date(2026, 1, 1), balance=10000,
                               annual_rate=20, monthly_payment=1000, source="register")  # fmt: skip
    ctx = client.get(reverse("web:debt")).context
    assert not ctx["aggregate"] and ctx["loans"][0]["name"] == "Card"
    assert ctx["base"]["months"] == 12  # annuity formula: 11.03 -> 12 payments
