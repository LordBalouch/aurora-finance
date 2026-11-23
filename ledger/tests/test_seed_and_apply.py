from pathlib import Path

import pytest
from django.core.management import call_command

from ledger.models import Account, Category, Rule, Transaction
from ledger.seed import CATEGORIES, RULES
from ledger.services import apply_rules, import_file

FIX = Path(__file__).parent / "fixtures"
pytestmark = pytest.mark.django_db


def test_every_seed_rule_points_to_a_seed_category():
    children = {c for kids in CATEGORIES.values() for c in kids}
    assert {r[1] for r in RULES} <= children
    assert len(children) == sum(len(k) for k in CATEGORIES.values())  # names are unique


def test_seed_is_idempotent_and_categorizes_imports():
    account = Account.objects.create(name="Everyday")
    call_command("seed_categories")
    call_command("seed_categories")
    assert Rule.objects.filter(source="seed").count() == len({(r[0], r[3], r[2]) for r in RULES})
    import_file((FIX / "in_out.csv").read_bytes(), "a.csv", account)
    cats = dict(Transaction.objects.values_list("description_clean", "category__name"))
    assert cats["REMA 1000 STORO"] == "Groceries"
    assert cats["Lønn ACME AS"] == "Salary"


def test_locked_category_is_never_overwritten():
    call_command("seed_categories")
    account = Account.objects.create(name="Everyday")
    import_file((FIX / "in_out.csv").read_bytes(), "a.csv", account)
    t = Transaction.objects.get(description_clean="REMA 1000 STORO")
    t.category = Category.objects.get(name="Eating out")
    t.category_locked = True
    t.save()
    apply_rules()
    t.refresh_from_db()
    assert t.category.name == "Eating out"


def test_user_rule_beats_seed_rule():
    call_command("seed_categories")
    account = Account.objects.create(name="Everyday")
    import_file((FIX / "in_out.csv").read_bytes(), "a.csv", account)
    Rule.objects.create(
        pattern="rema storo",
        match="merchant",
        category=Category.objects.get(name="Eating out"),
        priority=100,
    )
    apply_rules()
    assert (
        Transaction.objects.get(description_clean="REMA 1000 STORO").category.name == "Eating out"
    )
