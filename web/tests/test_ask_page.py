from datetime import date

import pytest
from django.urls import reverse

from ai import providers
from ai.tests.test_ask import FakeClaude
from ledger.models import Account, Category
from web.templatetags.text import answer_html

pytestmark = pytest.mark.django_db


@pytest.fixture
def data(add_transactions):
    food = Category.objects.create(name="Food", kind="variable")
    groceries = Category.objects.create(name="Groceries", parent=food, kind="variable")
    acc = Account.objects.create(name="Everyday")
    add_transactions(acc, [(date(2026, m, 3), "-1000", groceries) for m in range(1, 11)])


def test_page_without_ai_explains_how_to_turn_it_on(client):
    page = client.get(reverse("web:ask")).content.decode()
    assert "Ask your data" in page and "Settings" in page and 'name="question"' not in page


def test_question_gives_answer_lookups_and_chart(client, data, settings, monkeypatch):
    settings.ANTHROPIC_API_KEY = "test-key"
    fake = FakeClaude([("spending", {"group": "Food"})], "You spent **10 000 kr**.\n\n- Food")
    monkeypatch.setattr(providers, "claude_client", lambda: fake)
    page = client.get(reverse("web:ask")).content.decode()
    assert 'name="question"' in page and "data-question=" in page
    html = client.post(reverse("web:ask"), {"question": "Food?"}).content.decode()
    assert "<strong>10 000 kr</strong>" in html and "<li>Food</li>" in html
    assert "What the AI looked up (1)" in html and "spending(group=Food)" in html
    assert 'data-chart="ask_chart"' in html


def test_errors_are_shown_not_raised(client, settings):
    settings.ANTHROPIC_API_KEY = "test-key"
    html = client.post(reverse("web:ask"), {"question": ""}).content.decode()
    assert "Write a question first." in html


def test_answer_html_escapes_everything_first():
    html = answer_html("<script>x</script> **bold**\n- one\n- two\n\nEnd")
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert "<strong>bold</strong>" in html and "<ul><li>one</li><li>two</li></ul>" in html
    assert html.endswith("<p>End</p>")
