from datetime import date
from unittest.mock import patch

import pytest
from django.urls import reverse

from ledger.models import Account, Category, Transaction

pytestmark = pytest.mark.django_db


@pytest.fixture
def data(add_transactions):
    acc = Account.objects.create(name="Everyday")
    bills = Category.objects.create(name="Bills", kind="fixed")
    subs = Category.objects.create(name="Subscriptions", parent=bills, kind="fixed")
    food = Category.objects.create(name="Food", kind="variable")
    groceries = Category.objects.create(name="Groceries", parent=food, kind="variable")
    inc = Category.objects.create(name="Income", kind="income")
    salary = Category.objects.create(name="Salary", parent=inc, kind="income")
    rows = []
    for m in range(1, 9):
        rows += [
            (date(2026, m, 5), "-129", subs),
            (date(2026, m, 1), "20000", salary),
            (date(2026, m, 3 + m % 3), "-4000" if m < 8 else "-12000", groceries),
        ]
    add_transactions(acc, rows)
    Transaction.objects.filter(category=subs).update(merchant="netflix")
    return {"food": food}


def get(client, url):
    with patch("web.insights_page.date") as fake, patch("web.views.date") as fake2:
        fake.today.return_value = fake2.today.return_value = date(2026, 9, 10)
        return client.get(url)


def test_insights_without_data(client):
    assert not client.get(reverse("web:insights")).context["has_data"]


def test_insights_page_lists_recurring_anomalies_and_flow(client, data):
    ctx = get(client, reverse("web:insights")).context
    assert [r["name"] for r in ctx["recurring"]] == ["netflix"]
    assert ctx["recurring"][0]["url"].endswith("merchant=netflix")
    assert ctx["anomalies"][0]["group"] == "Food"
    assert f"category={data['food'].pk}" in ctx["anomalies"][0]["url"]
    assert {n["name"] for n in ctx["sankey"]["nodes"]} >= {"Salary", "Food", "Left over"}
    assert ctx["flow_insight"].startswith("Income covered all spending")
    assert ctx["heatmap"]["kind"] == "heatmap" and len(ctx["heatmap"]["y"]) == 7


def test_dashboard_bars_link_to_transactions_and_shows_cards(client, data):
    ctx = get(client, reverse("web:dashboard")).context
    assert f"category={data['food'].pk}" in ctx["categories"]["links"][0][0]  # Food is largest
    assert ctx["recurring_count"] == 1 and ctx["forecast"] is None
    assert ctx["data_until"].month == 8  # data ends before the current month: no forecast


def test_transactions_filter_by_merchant(client, data):
    response = client.get(reverse("web:transactions") + "?merchant=netflix")
    assert response.context["totals"]["n"] == 8
