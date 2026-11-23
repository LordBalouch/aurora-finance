from pathlib import Path

import pytest
from django.core.management import call_command

from ledger.models import Account

FIX = Path(__file__).parent / "fixtures"


@pytest.mark.django_db
def test_command_imports_and_is_idempotent(capsys):
    files = [str(FIX / "in_out.csv"), str(FIX / "signed.csv")]
    call_command("import_files", *files, account="Everyday", bank="DNB")
    call_command("import_files", *files, account="Everyday")
    account = Account.objects.get(name="Everyday")
    assert account.bank == "DNB" and account.transactions.count() == 6
    assert "+0 new, 6 skipped" in capsys.readouterr().out
