import os
import socket
from pathlib import Path

import pytest
from django.urls import reverse

from desktop import launcher


def test_data_dir_per_platform(monkeypatch, tmp_path):
    monkeypatch.delenv("AURORA_DATA_DIR", raising=False)
    monkeypatch.setattr(launcher.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(launcher.sys, "platform", "darwin")
    assert launcher.data_dir() == tmp_path / "Library" / "Application Support" / "Aurora"
    monkeypatch.setattr(launcher.sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    assert launcher.data_dir() == tmp_path / "Roaming" / "Aurora"
    monkeypatch.setattr(launcher.sys, "platform", "linux")
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    assert launcher.data_dir() == tmp_path / ".local" / "share" / "aurora"
    monkeypatch.setenv("AURORA_DATA_DIR", str(tmp_path / "mine"))
    assert launcher.data_dir() == tmp_path / "mine"


def test_configure_uses_the_folder_and_keeps_one_secret(monkeypatch, tmp_path):
    for name in ("DB_PATH", "LOCAL_SETTINGS_FILE", "DEBUG", "SECRET_KEY", "AURORA_DESKTOP"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(os, "environ", dict(os.environ))
    folder = tmp_path / "Aurora"
    launcher.configure(folder)
    assert os.environ["DB_PATH"] == str(folder / "aurora.sqlite3")
    assert os.environ["DEBUG"] == "False" and os.environ["AURORA_DESKTOP"] == "True"
    assert os.environ["ALLOWED_HOSTS"] == "127.0.0.1,localhost"
    key = os.environ["SECRET_KEY"]
    assert len(key) > 40 and launcher.secret_key(folder) == key  # same key next start
    assert oct((folder / "secret_key.txt").stat().st_mode)[-3:] == "600"


def test_free_port_skips_a_busy_one(monkeypatch):
    with socket.socket() as busy:
        busy.bind(("127.0.0.1", 0))
        busy.listen()
        port = busy.getsockname()[1]
        monkeypatch.setattr(launcher, "PORTS", range(port, port + 3))
        assert launcher.free_port() != port


def test_running_finds_nothing_on_closed_ports(monkeypatch):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    monkeypatch.setattr(launcher, "PORTS", range(port, port + 1))
    assert launcher.running() is None


@pytest.mark.django_db
def test_ping_and_quit(client, settings, monkeypatch):
    assert client.get(reverse("web:ping")).content == b"aurora"
    assert client.post(reverse("web:quit")).status_code == 404  # only in the desktop app
    settings.DESKTOP = True
    stopped = []
    monkeypatch.setattr("web.desktop.threading.Timer", lambda delay, fn, args: SimpleTimer(stopped))
    response = client.post(reverse("web:quit"))
    assert b"Aurora has stopped" in response.content and stopped == [True]
    assert "Quit Aurora" in client.get(reverse("web:settings")).content.decode()


class SimpleTimer:
    def __init__(self, record):
        self.record = record

    def start(self):
        self.record.append(True)


def test_spec_lists_our_packages():
    spec = (Path(launcher.__file__).parent / "aurora.spec").read_text()
    for package in ("config", "ledger", "web", "ai", "insights"):
        assert f'"{package}"' in spec
