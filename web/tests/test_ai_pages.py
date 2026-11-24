from datetime import date

import pytest
from django.urls import reverse

from ai import advisor
from ai.tests.test_advisor import FakeClient
from ledger.models import Account, Category, TaxYear

pytestmark = pytest.mark.django_db


@pytest.fixture
def data(add_transactions):
    acc = Account.objects.create(name="Everyday")
    food = Category.objects.create(name="Food", kind="variable")
    groceries = Category.objects.create(name="Groceries", parent=food, kind="variable")
    inc = Category.objects.create(name="Income", kind="income")
    salary = Category.objects.create(name="Salary", parent=inc, kind="income")
    rows = []
    for m in range(1, 9):
        rows += [(date(2026, m, 1), "30000", salary), (date(2026, m, 3), "-4000", groceries)]
    add_transactions(acc, rows)
    TaxYear.objects.create(year=2025, debt=500000, interest_expense=30000, total_income=400000)


@pytest.fixture
def fake(settings, monkeypatch):
    settings.ANTHROPIC_API_KEY = "test-key"
    client = FakeClient()
    monkeypatch.setattr(advisor, "_client", lambda: client)
    return client


@pytest.mark.parametrize(
    "card", ["overview", "month_story", "trends", "recurring", "anomalies", "money_flow",
             "debt", "years", "budget"],
)  # fmt: skip
def test_every_card_sends_its_numbers_and_shows_tips(client, data, fake, card):
    response = client.post(reverse("web:ai_ask", args=[card]))
    assert response.status_code == 200
    html = response.content.decode()
    assert "Rentene er høye." in html and "What the AI saw" in html
    assert "New take" in html and "AI · new take" in html
    assert len(fake.calls) == 1


def test_numbers_are_computed_on_the_server(client, data, fake):
    client.post(reverse("web:ai_ask", args=["overview"]), {"income": "999999999"})
    assert "999999999" not in fake.calls[0]["messages"][0]["content"]
    assert "Food" in fake.calls[0]["messages"][0]["content"]


def test_unknown_card_and_get_are_refused(client, fake):
    assert client.post("/ai/nope/").status_code == 404
    assert client.get(reverse("web:ai_ask", args=["overview"])).status_code == 405


def test_without_key_button_is_disabled_and_answer_explains(client, data, settings):
    settings.ANTHROPIC_API_KEY = ""
    page = client.get(reverse("web:dashboard")).content.decode()
    assert "disabled" in page and "ANTHROPIC_API_KEY" in page and "Aurora's take" in page
    answer = client.post(reverse("web:ai_ask", args=["overview"])).content.decode()
    assert "ANTHROPIC_API_KEY" in answer
