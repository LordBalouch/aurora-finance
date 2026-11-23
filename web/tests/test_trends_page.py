from datetime import date
from unittest.mock import patch

import pytest
from django.urls import reverse

from ledger.models import Account, Category

pytestmark = pytest.mark.django_db


def test_trends_without_data_asks_for_import(client):
    response = client.get(reverse("web:trends"))
    assert response.status_code == 200 and not response.context["has_data"]


def test_trends_page_shows_groups_and_split(client, add_transactions):
    acc = Account.objects.create(name="Everyday")
    housing = Category.objects.create(name="Housing", kind="fixed")
    rent = Category.objects.create(name="Rent", parent=housing, kind="fixed")
    food = Category.objects.create(name="Food", kind="variable")
    groceries = Category.objects.create(name="Groceries", parent=food, kind="variable")
    rows = []
    for m in range(1, 7):
        rows += [(date(2026, m, 1), "-8000", rent), (date(2026, m, 2), f"-{1000 * m}", groceries)]
    add_transactions(acc, rows)
    with patch("web.trends.date") as fake:
        fake.today.return_value = date(2026, 7, 10)
        response = client.get(reverse("web:trends"))
    ctx = response.context
    assert ctx["stacked"]["stack"] and [s["name"] for s in ctx["stacked"]["series"]] == [
        "Housing",
        "Food",
    ]
    assert [s["name"] for s in ctx["split"]["series"]] == ["Fixed", "Variable"]
    assert "from=2026-01-01" in ctx["stacked"]["links"][0][0]  # Housing, January
    food_card = next(g for g in ctx["multiples"] if g["name"] == "Food")
    assert food_card["change"] == 150  # (4+5+6)/(1+2+3) - 1
    assert "Food rose the most" in ctx["stack_insight"]
    assert ctx["multiples"][0]["spark"]["y_max"] == 8000
    assert 'data-chart="group-0"' in response.content.decode()
