from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from ledger.models import Account, ImportBatch, Transaction
from web import imports

FIX = Path(__file__).resolve().parents[2] / "ledger" / "tests" / "fixtures"
pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def uploads_in_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(imports, "UPLOADS", tmp_path / "uploads")


def upload(client, **extra):
    data = (FIX / "in_out.csv").read_bytes()
    return client.post(
        reverse("web:import"),
        {"file": SimpleUploadedFile("in_out.csv", data), **extra},
    )


def test_preview_then_confirm_imports_into_new_account(client):
    response = upload(client, new_account_name="Everyday", bank="DNB")
    assert response.status_code == 200
    pending = response.context["pending"]
    assert "Import 4 transactions" in response.content.decode()
    assert Transaction.objects.count() == 0  # preview writes nothing

    response = client.post(reverse("web:import_confirm"), pending)
    account = Account.objects.get(name="Everyday")
    assert response.status_code == 302 and f"account={account.pk}" in response.url
    assert account.bank == "DNB" and account.transactions.count() == 4
    assert not (imports.UPLOADS / f"{pending['sha']}.csv").exists()


def test_needs_an_account(client):
    response = upload(client)
    assert "Choose an account" in response.content.decode()


UNKNOWN = b"When;What;In;Out\n01.02.2026;Shop;;10,00\n03.02.2026;Pay;100,00;\n"


def test_unknown_columns_ask_which_column_is_which(client):
    response = client.post(
        reverse("web:import"),
        {"file": SimpleUploadedFile("x.csv", UNKNOWN), "new_account_name": "A", "bank": "Acme"},
    )
    html = response.content.decode()
    assert "New file layout" in html and 'name="col_date"' in html and "<th>When</th>" in html
    assert '<option value="In" selected>' in html  # In and Out are recognised, the rest not
    assert '<option value="Out" selected>' in html


def test_chosen_columns_give_a_preview_and_are_remembered(client):
    from ledger.models import BankFormat

    client.post(reverse("web:import"), {"file": SimpleUploadedFile("x.csv", UNKNOWN),
                                        "new_account_name": "A"})  # fmt: skip
    sha = __import__("hashlib").sha256(UNKNOWN).hexdigest()
    base = {"sha": sha, "file_name": "x.csv", "new_account_name": "A", "format_name": "Acme"}
    bad = client.post(reverse("web:import_map"), {**base, "col_date": "When"}).content.decode()
    assert "Choose a date column" in bad and "New file layout" in bad
    cols = {"col_date": "When", "col_description": "What", "col_in": "In", "col_out": "Out"}
    html = client.post(reverse("web:import_map"), {**base, **cols}).content.decode()
    assert "Preview" in html and "Import 2 transactions" in html and "Acme" in html
    assert BankFormat.objects.get().columns == {
        "date": "When", "description": "What", "in": "In", "out": "Out"
    }  # fmt: skip
    # The next file with these columns goes straight to the preview.
    upload_again = {"file": SimpleUploadedFile("y.csv", UNKNOWN), "new_account_name": "A"}
    again = client.post(reverse("web:import"), upload_again).content.decode()
    assert "Import 2 transactions" in again and "Your file layouts" in again
    client.post(reverse("web:format_delete", args=[BankFormat.objects.get().pk]))
    assert not BankFormat.objects.exists()


def test_map_rejects_a_missing_file(client):
    response = client.post(reverse("web:import_map"), {"sha": "0" * 64})
    assert response.status_code == 302


def test_unreadable_file_shows_error(client):
    response = client.post(
        reverse("web:import"),
        {"file": SimpleUploadedFile("x.csv", b" \n"), "new_account_name": "A"},
    )
    assert "The file is empty" in response.content.decode()


def test_confirm_rejects_tampered_sha(client):
    response = client.post(reverse("web:import_confirm"), {"sha": "../../etc/passwd"})
    assert response.status_code == 302 and response.url == reverse("web:import")
    assert ImportBatch.objects.count() == 0


def test_undo(client):
    pending = upload(client, new_account_name="Everyday").context["pending"]
    client.post(reverse("web:import_confirm"), pending)
    batch = ImportBatch.objects.get()
    client.post(reverse("web:import_undo", args=[batch.pk]))
    assert Transaction.objects.count() == 0 and ImportBatch.objects.count() == 0


def test_undo_requires_post(client):
    assert client.get(reverse("web:import_undo", args=[1])).status_code == 405
