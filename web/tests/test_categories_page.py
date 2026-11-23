from pathlib import Path

import pytest
from django.core.management import call_command
from django.urls import reverse

from ledger.models import Account, Category, Rule, Transaction
from ledger.services import import_file

FIX = Path(__file__).resolve().parents[2] / "ledger" / "tests" / "fixtures"
pytestmark = pytest.mark.django_db


@pytest.fixture
def data():
    call_command("seed_categories")
    account = Account.objects.create(name="Everyday")
    import_file((FIX / "in_out.csv").read_bytes(), "a.csv", account)
    return account


def test_inbox_lists_uncategorized_groups_split_by_direction(client, data):
    response = client.get(reverse("web:categories"))
    inbox = response.context["inbox"]
    vipps = [g for g in inbox if g["merchant"] == "vipps kaffebar"]
    assert len(vipps) == 1 and vipps[0]["n"] == 2 and vipps[0]["sign"] == "out"
    assert response.context["coverage"]["done"] == 2  # REMA + salary


def test_assign_creates_user_rule_and_applies_it(client, data):
    eating_out = Category.objects.get(name="Eating out")
    response = client.post(
        reverse("web:assign"),
        {"merchant": "vipps kaffebar", "sign": "out", "category": eating_out.pk},
        HTTP_HX_REQUEST="true",
    )
    assert response.status_code == 200 and "2 transactions" in response.content.decode()
    rule = Rule.objects.get(pattern="vipps kaffebar")
    assert (rule.source, rule.match, rule.priority) == ("user", "merchant", 100)
    assert Transaction.objects.filter(category=eating_out).count() == 2


def test_assign_rejects_parent_category_and_bad_sign(client, data):
    parent = Category.objects.get(name="Food", parent=None)
    assert (
        client.post(
            reverse("web:assign"), {"merchant": "x", "sign": "out", "category": parent.pk}
        ).status_code
        == 404
    )
    child = Category.objects.get(name="Groceries")
    assert (
        client.post(
            reverse("web:assign"), {"merchant": "x", "sign": "up", "category": child.pk}
        ).status_code
        == 400
    )


def test_transactions_filter_by_category_and_uncategorized(client, data):
    food = Category.objects.get(name="Food", parent=None)
    page = client.get(reverse("web:transactions"), {"category": food.pk}).context["page"]
    assert [t.description_clean for t in page] == ["REMA 1000 STORO"]
    none = client.get(reverse("web:transactions"), {"category": "none"}).context["totals"]["n"]
    assert none == 2
