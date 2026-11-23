from datetime import date

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from ledger.demo import generate
from ledger.models import Account, Budget, DebtBalance, Goal, TaxYear, Transaction

END = date(2026, 11, 23)


def test_generate_is_reproducible_and_spans_two_years():
    rows = generate(END)
    assert rows == generate(END)
    assert rows != generate(END, seed=8)
    assert min(r.date for r in rows) == date(2024, 12, 1)
    assert max(r.date for r in rows) <= END
    assert {r.account for r in rows} == {"Brukskonto", "Regningskonto"}


def test_transfers_between_own_accounts_balance_out():
    transfers = [r for r in generate(END) if "mellom egne konti" in r.description]
    assert sum(r.amount for r in transfers) == 0


@pytest.mark.django_db
def test_command_fills_an_empty_database():
    call_command("make_demo_data", end=END)
    total = Transaction.objects.count()
    assert total > 800
    assert Transaction.objects.filter(category=None).count() / total < 0.02
    assert Account.objects.count() == 2
    assert TaxYear.objects.count() == 2
    assert DebtBalance.objects.count() == 2
    assert Budget.objects.exists()
    assert Goal.objects.count() == 2


@pytest.mark.django_db
def test_command_refuses_a_database_with_transactions():
    call_command("make_demo_data", end=END)
    with pytest.raises(CommandError, match="empty"):
        call_command("make_demo_data", end=END)
