from pathlib import Path

import pytest
from django.urls import reverse

from ledger.models import Account
from ledger.services import import_file
from web import transactions

FIX = Path(__file__).resolve().parents[2] / "ledger" / "tests" / "fixtures"
pytestmark = pytest.mark.django_db


@pytest.fixture
def data():
    account = Account.objects.create(name="Everyday")
    import_file((FIX / "in_out.csv").read_bytes(), "a.csv", account)
    import_file((FIX / "signed.csv").read_bytes(), "b.csv", account)
    return account


def test_empty_state(client):
    assert "No transactions yet" in client.get(reverse("web:transactions")).content.decode()


def test_search_matches_clean_and_raw_text(client, data):
    page = client.get(reverse("web:transactions"), {"q": "rema"}).context["page"]
    assert [t.description_clean for t in page] == ["REMA 1000 STORO"]
    page = client.get(reverse("web:transactions"), {"q": "4821"}).context["page"]
    assert len(page.object_list) == 1


def test_totals_follow_the_filter(client, data):
    totals = client.get(reverse("web:transactions"), {"from": "2026-11-21"}).context["totals"]
    assert totals["n"] == 3 and totals["money_in"] is None


def test_htmx_returns_partials(client, data, monkeypatch):
    monkeypatch.setattr(transactions, "PAGE_SIZE", 2)
    url = reverse("web:transactions")
    results = client.get(url, HTTP_HX_REQUEST="true")
    assert (
        "<html" not in results.content.decode()
        and 'hx-trigger="revealed"' in results.content.decode()
    )
    more = client.get(url, {"page": 2}, HTTP_HX_REQUEST="true")
    assert more.content.decode().lstrip().startswith("<tr")


def test_bad_dates_are_ignored(client, data):
    assert client.get(reverse("web:transactions"), {"from": "nope"}).status_code == 200
