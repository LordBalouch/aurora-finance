from pathlib import Path

import pytest

from ledger.models import Account, Transaction
from ledger.services import import_file, preview, undo_import

FIX = Path(__file__).parent / "fixtures"
pytestmark = pytest.mark.django_db


@pytest.fixture
def account():
    return Account.objects.create(name="Everyday")


def test_import_then_reimport_adds_nothing(account):
    data = (FIX / "in_out.csv").read_bytes()
    first = import_file(data, "in_out.csv", account)
    assert first.rows_imported == 4
    second = import_file(data, "in_out.csv", account)
    assert (second.rows_imported, second.rows_duplicate) == (0, 4)
    assert Transaction.objects.count() == 4


def test_overlapping_file_only_adds_the_new_rows(account):
    data = (FIX / "in_out.csv").read_bytes()
    import_file(data, "a.csv", account)
    extra = data + b'"22.11.2026";"Vy billett";"22.11.2026";"39,00";""\n'
    batch = import_file(extra, "b.csv", account)
    assert (batch.rows_imported, batch.rows_duplicate) == (1, 4)


def test_preview_writes_nothing_and_flags_same_file(account):
    data = (FIX / "in_out.csv").read_bytes()
    result = preview(data, account)
    assert len(result.new) == 4 and Transaction.objects.count() == 0
    import_file(data, "in_out.csv", account)
    assert preview(data, account).already_imported is not None


def test_same_rows_in_another_account_are_not_duplicates(account):
    data = (FIX / "in_out.csv").read_bytes()
    import_file(data, "x.csv", account)
    other = Account.objects.create(name="Savings")
    assert import_file(data, "x.csv", other).rows_imported == 4


def test_undo_removes_only_that_batch(account):
    a = import_file((FIX / "in_out.csv").read_bytes(), "a.csv", account)
    import_file((FIX / "signed.csv").read_bytes(), "b.csv", account)
    assert undo_import(a) == 4
    assert Transaction.objects.count() == 2
