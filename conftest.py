from decimal import Decimal

import pytest


@pytest.fixture(autouse=True)
def no_real_ai(settings, tmp_path):
    """Tests never call a real model or read the owner's settings, whatever is local."""
    settings.AI_PROVIDER = "anthropic"
    settings.ANTHROPIC_API_KEY = ""
    settings.OPENAI_BASE_URL = settings.OPENAI_API_KEY = settings.OPENAI_MODEL = ""
    settings.LOCAL_SETTINGS_FILE = str(tmp_path / "settings.json")


@pytest.fixture
def add_transactions(db):
    """add_transactions(account, [(date, "amount", category), ...]) -> created rows."""
    from ledger.models import ImportBatch, Transaction

    def add(account, rows):
        batch = ImportBatch.objects.create(
            account=account, file_name="t.csv", file_sha256="0" * 64, importer="test",
            rows_total=len(rows), rows_imported=len(rows), rows_duplicate=0,
        )  # fmt: skip
        return [
            Transaction.objects.create(
                account=account,
                import_batch=batch,
                date=day,
                amount=Decimal(amount),
                description_raw="x",
                description_clean="x",
                category=cat,
                fingerprint=f"{batch.pk}-{i}",
            )  # fmt: skip
            for i, (day, amount, cat) in enumerate(rows)
        ]

    return add
