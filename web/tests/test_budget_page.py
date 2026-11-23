from datetime import date
from unittest.mock import patch

import pytest
from django.urls import reverse

from ledger.models import Account, Budget, Category, Goal

pytestmark = pytest.mark.django_db


@pytest.fixture
def data(add_transactions):
    acc = Account.objects.create(name="Everyday")
    food = Category.objects.create(name="Food", kind="variable")
    groceries = Category.objects.create(name="Groceries", parent=food, kind="variable")
    rows = [(date(2026, m, 10), "-4000", groceries) for m in range(1, 7)]
    rows.append((date(2026, 7, 3), "-3500", groceries))
    add_transactions(acc, rows)
    return food


def get(client, url):
    with patch("web.budget.date") as fake:
        fake.today.return_value = date(2026, 7, 10)
        return client.get(url)


def test_empty_month_offers_suggestion(client, data):
    ctx = get(client, reverse("web:budget")).context
    assert not ctx["has_budget"] and ctx["suggestion"] == {"Food": 4000}


def test_create_from_history_then_progress(client, data):
    client.post(reverse("web:budget_create"), {"month": "2026-07", "source": "history"})
    assert Budget.objects.get(category=data).amount == 4000
    ctx = get(client, reverse("web:budget") + "?month=2026-07").context
    row = ctx["rows"][0]
    assert row["group"] == "Food" and row["spent"] == 3500 and row["status"] == "at risk"
    assert ctx["burndown"]["series"][0]["data"][2] == 3500  # 3 July
    assert b'<span class="kpi-value num">1</span>' in get(client, "/budget/?month=2026-07").content


def test_save_changes_and_removes(client, data):
    Budget.objects.create(month=date(2026, 7, 1), category=data, amount=4000)
    client.post(reverse("web:budget_save"), {"month": "2026-07", f"amount_{data.pk}": "6 000"})
    assert Budget.objects.get(category=data).amount == 6000
    client.post(reverse("web:budget_save"), {"month": "2026-07", f"amount_{data.pk}": ""})
    assert not Budget.objects.exists()


def test_copy_previous_and_year_view(client, data):
    Budget.objects.create(month=date(2026, 6, 1), category=data, amount=2000)
    client.post(reverse("web:budget_create"), {"month": "2026-07", "source": "previous"})
    ctx = get(client, reverse("web:budget") + "?month=2026-07").context
    assert ctx["year_view"]["y"] == ["Food"] and ctx["year_view"]["cells"][0][2] == 200


def test_goals(client):
    client.post(reverse("web:goal_add"), {"name": "Buffer", "target_amount": "30000",
                                         "saved": "10000", "monthly": "5000"})  # fmt: skip
    with patch("web.budget.date") as fake:
        fake.today.return_value = date(2026, 1, 1)
        goal = client.get(reverse("web:budget")).context["goals"][0]
    assert goal["months"] == 4 and goal["share"] == pytest.approx(33.3)
    client.post(reverse("web:goal_delete", args=[Goal.objects.get().pk]))
    assert not Goal.objects.exists()
