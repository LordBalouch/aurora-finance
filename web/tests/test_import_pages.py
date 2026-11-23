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


def test_unreadable_file_shows_error(client):
    response = client.post(
        reverse("web:import"),
        {"file": SimpleUploadedFile("x.csv", b"Foo;Bar\n1;2\n"), "new_account_name": "A"},
    )
    assert "Could not recognise the columns" in response.content.decode()


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
