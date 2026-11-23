import json
from datetime import date
from unittest.mock import patch

import pytest
from django.urls import reverse

from ledger.models import Account, Category

pytestmark = pytest.mark.django_db


def test_dashboard_renders_sample_with_charts(client):
    response = client.get(reverse("web:dashboard"))
    assert response.status_code == 200
    html = response.content.decode()
    assert "Sample data" in html
    for chart_id in ("trend", "categories", "spark-income", "spark-rate"):
        assert f'data-chart="{chart_id}"' in html
        assert f'id="{chart_id}"' in html


def test_spending_increase_is_marked_bad(client):
    response = client.get(reverse("web:dashboard"))
    spending = next(k for k in response.context["kpis"] if k["key"] == "spending")
    # Sample: Oct 43 800 -> Nov 40 900, a decrease, which is good for spending.
    assert spending["delta"]["up"] is False
    assert spending["delta"]["good"] is True
    json.dumps(spending["spark"])  # spec must be JSON-serialisable


def test_savings_rate_delta_is_percentage_points(client):
    response = client.get(reverse("web:dashboard"))
    rate = next(k for k in response.context["kpis"] if k["key"] == "rate")
    assert rate["delta"]["unit"] == "pp"
    assert rate["delta"]["value"] < 10  # 15.4 % -> 21.8 % is +6.4 pp, not +41.6 %


def test_other_category_is_last(client):
    response = client.get(reverse("web:dashboard"))
    assert response.context["categories"]["x"][-1] == "Other"


def test_dashboard_uses_real_data_when_there_is_some(client, add_transactions):
    acc = Account.objects.create(name="Everyday")
    inc = Category.objects.create(name="Income", kind="income")
    salary = Category.objects.create(name="Salary", parent=inc, kind="income")
    money = Category.objects.create(name="Money", kind="variable")
    friends = Category.objects.create(name="Friends & family", parent=money, kind="variable")
    food = Category.objects.create(name="Food", kind="variable")
    groceries = Category.objects.create(name="Groceries", parent=food, kind="variable")
    rows = []
    for m in range(1, 7):
        rows += [(date(2026, m, 1), "40000", salary), (date(2026, m, 2), "-10000", groceries)]
    rows += [(date(2026, 6, 3), "-20000", groceries), (date(2026, 6, 4), "700", friends)]
    add_transactions(acc, rows)
    with patch("web.views.date") as fake:
        fake.today.return_value = date(2026, 7, 10)
        response = client.get(reverse("web:dashboard") + "?period=3m")
    ctx = response.context
    assert not ctx["is_sample"] and "Sample data" not in response.content.decode()
    spending = next(k for k in ctx["kpis"] if k["key"] == "spending")
    assert spending["value"] == 30000 and spending["average"] == 10000
    assert spending["delta"]["up"] and not spending["delta"]["good"]
    assert ctx["trend"]["x"] == ["Apr 26", "May 26", "Jun 26"]
    assert ctx["netted"][0]["net"] == 700  # not in income
    assert "June 2026" in ctx["trend_insight"]
    net = next(k for k in ctx["kpis"] if k["key"] == "net")
    assert net["delta"]["unit"] == "kr" and net["delta"]["value"] == 20000  # 30 000 -> 10 000
    rate = next(k for k in ctx["kpis"] if k["key"] == "rate")
    assert rate["average"] == 75  # average net 30 000 / average income 40 000


def test_unchanged_value_is_neutral_not_down():
    from web.views import _delta

    flat = _delta(39_847.5, 39_847.5, higher_is_good=True)
    assert flat["flat"] and flat["value"] == 0
    assert not _delta(110, 100, higher_is_good=True)["flat"]
    assert _delta(100.2, 100, higher_is_good=True, unit="kr")["flat"]
