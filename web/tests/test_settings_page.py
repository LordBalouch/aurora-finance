import sqlite3
from datetime import date

import pytest
from django.urls import reverse

from ai import config
from ledger.models import Account, Transaction

pytestmark = pytest.mark.django_db


def test_page_shows_settings_but_never_a_key(client, settings):
    settings.ANTHROPIC_API_KEY = "sk-ant-secret-9876"
    page = client.get(reverse("web:settings")).content.decode()
    assert "Settings" in page and "ends in …9876" in page
    assert "sk-ant-secret" not in page


def _form(**overrides):
    data = {
        "provider": "ollama", "language": "English", "about_me": "Two kids",
        "anthropic_key": "", "ai_model": "claude-opus-5-5",
        "ollama_url": "http://localhost:11434", "ollama_model": "gpt-oss:20b",
        "ollama_think": "on", "openai_base_url": "", "openai_key": "", "openai_model": "",
    }  # fmt: skip
    return {**data, **overrides}


def test_saving_writes_the_local_file_and_wins_over_env(client, settings):
    response = client.post(reverse("web:settings"), _form(anthropic_key="sk-new-1111"))
    assert response.status_code == 302
    assert config.conf("AI_PROVIDER") == "ollama" and config.conf("OLLAMA_THINK") is True
    assert config.conf("AI_ABOUT_ME") == "Two kids"
    assert config.conf("ANTHROPIC_API_KEY") == "sk-new-1111"
    # An empty key field keeps the stored key; "forget" removes it and .env applies again.
    client.post(reverse("web:settings"), _form(provider="anthropic"))
    assert config.conf("ANTHROPIC_API_KEY") == "sk-new-1111"
    settings.ANTHROPIC_API_KEY = "from-env"
    client.post(reverse("web:settings"), _form(forget_keys="on"))
    assert config.conf("ANTHROPIC_API_KEY") == "from-env"


def test_openai_needs_url_and_model(client):
    page = client.post(reverse("web:settings"), _form(provider="openai")).content.decode()
    assert "needs a base URL and a model" in page
    assert config.saved() == {}


def test_settings_file_is_private(client, settings):
    client.post(reverse("web:settings"), _form())
    from pathlib import Path

    assert oct(Path(settings.LOCAL_SETTINGS_FILE).stat().st_mode)[-3:] == "600"


def test_test_button_reports_success_and_failure(client, settings, monkeypatch):
    from web import settings_page

    html = client.post(reverse("web:settings_test_ai")).content.decode()
    assert "msg-warning" in html  # no AI configured
    settings.ANTHROPIC_API_KEY = "k"
    monkeypatch.setattr(settings_page, "complete_json", lambda *a, **k: ("{}", 1, 1))
    html = client.post(reverse("web:settings_test_ai")).content.decode()
    assert "It works" in html and "msg-success" in html


@pytest.fixture
def one_row(add_transactions):
    acc = Account.objects.create(name="Everyday")
    add_transactions(acc, [(date(2026, 1, 2), "-100", None)])


@pytest.mark.django_db(transaction=True)
def test_backup_then_restore_round_trip(client, settings, tmp_path, one_row, add_transactions):
    settings.DATA_DIR = tmp_path
    response = client.get(reverse("web:backup"))
    assert response["Content-Disposition"].startswith('attachment; filename="aurora-backup-')
    backup = tmp_path / "b.sqlite3"
    backup.write_bytes(b"".join(response.streaming_content))
    assert sqlite3.connect(backup).execute(
        "select count(*) from ledger_transaction"
    ).fetchone() == (1,)

    add_transactions(Account.objects.get(), [(date(2026, 1, 3), "-50", None)])
    assert Transaction.objects.count() == 2
    with backup.open("rb") as f:
        response = client.post(reverse("web:restore"), {"backup": f, "confirm": "yes"}, follow=True)
    assert "Backup restored: 1 transactions" in response.content.decode()
    assert Transaction.objects.count() == 1
    assert len(list((tmp_path / "backups").glob("before-restore-*.sqlite3"))) == 1


def test_restore_refuses_other_files_and_needs_confirmation(client, settings, tmp_path):
    settings.DATA_DIR = tmp_path
    junk = tmp_path / "junk.sqlite3"
    junk.write_bytes(b"not a database at all" * 100)
    with junk.open("rb") as f:
        page = client.post(reverse("web:restore"), {"backup": f}, follow=True).content.decode()
    assert "tick the box" in page
    with junk.open("rb") as f:
        page = client.post(reverse("web:restore"), {"backup": f, "confirm": "yes"},
                           follow=True).content.decode()  # fmt: skip
    assert "not a SQLite database" in page
    empty = tmp_path / "empty.sqlite3"
    sqlite3.connect(empty).execute("create table x (a)")
    with empty.open("rb") as f:
        page = client.post(reverse("web:restore"), {"backup": f, "confirm": "yes"},
                           follow=True).content.decode()  # fmt: skip
    assert "not an Aurora backup" in page
