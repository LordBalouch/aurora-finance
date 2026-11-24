"""Aurora as a desktop app: start a local server and open the browser.

Everything stays on this computer. The data folder is the user's own (override with
AURORA_DATA_DIR):
- macOS: ~/Library/Application Support/Aurora
- Windows: %APPDATA%\\Aurora
- Linux: ~/.local/share/aurora

The server listens on 127.0.0.1 only, so nothing else on the network can reach it. Run from
source with `python desktop/launcher.py`, or as the packaged app (`make app`).
"""

import os
import secrets
import socket
import sys
import threading
import time
import webbrowser
from io import StringIO
from pathlib import Path

HOST = "127.0.0.1"
PORTS = range(8765, 8785)


def data_dir() -> Path:
    if os.environ.get("AURORA_DATA_DIR"):
        return Path(os.environ["AURORA_DATA_DIR"]).expanduser()
    home = Path.home()
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / "Aurora"
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", home)) / "Aurora"
    return Path(os.environ.get("XDG_DATA_HOME", home / ".local" / "share")) / "aurora"


def secret_key(folder: Path) -> str:
    """One random key per installation, kept in the data folder."""
    path = folder / "secret_key.txt"
    if not path.exists():
        path.write_text(secrets.token_urlsafe(50))
        path.chmod(0o600)
    return path.read_text().strip()


def running() -> str | None:
    """The URL of an Aurora that is already running, so a second launch just opens it."""
    from urllib.request import urlopen

    for port in PORTS:
        try:
            # The first request loads all of Django and pandas: give it a few seconds.
            with urlopen(f"http://{HOST}:{port}/ping/", timeout=5) as response:
                if response.read() == b"aurora":
                    return f"http://{HOST}:{port}/"
        except OSError:
            continue
    return None


def free_port() -> int:
    for port in PORTS:
        with socket.socket() as s:
            if s.connect_ex((HOST, port)) != 0:
                return port
    raise SystemExit(f"No free port between {PORTS.start} and {PORTS.stop - 1}.")


def warm_up_and_open(url: str) -> None:
    """Load the first page once (it imports pandas and every view), then open the browser,
    so the user never waits on a blank tab."""
    from urllib.request import urlopen

    for _ in range(120):
        try:
            with urlopen(url, timeout=60):
                break
        except OSError:
            time.sleep(0.5)
    if not os.environ.get("AURORA_NO_BROWSER"):
        webbrowser.open(url)


def configure(folder: Path) -> None:
    """Environment for Django before it is imported: production mode, the user's folder."""
    folder.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    os.environ["AURORA_DATA_DIR"] = str(folder)
    os.environ.setdefault("DB_PATH", str(folder / "aurora.sqlite3"))
    os.environ.setdefault("LOCAL_SETTINGS_FILE", str(folder / "settings.json"))
    os.environ["DEBUG"] = "False"
    os.environ["SECRET_KEY"] = secret_key(folder)
    os.environ["ALLOWED_HOSTS"] = "127.0.0.1,localhost"
    os.environ["AURORA_DESKTOP"] = "True"


def prepare() -> None:
    """Create or update the database and the built-in categories (both are idempotent)."""
    import django
    from django.core.management import call_command

    django.setup()
    call_command("migrate", verbosity=0, interactive=False)
    call_command("seed_categories", stdout=StringIO())


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)  # the packaged app writes to a pipe
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    sys.path.insert(0, str(root))
    url = running()
    if url:
        print(f"Aurora is already running: {url}")
        webbrowser.open(url)
        return
    folder = data_dir()
    configure(folder)
    print(f"Aurora: data in {folder}")
    prepare()

    from waitress import serve

    from config.wsgi import application

    port = free_port()
    url = f"http://{HOST}:{port}/"
    threading.Thread(target=warm_up_and_open, args=[url], daemon=True).start()
    print(f"Aurora is running at {url}  (close this window or press Ctrl+C to stop)")
    try:
        serve(application, host=HOST, port=port, threads=4, channel_timeout=900)
    except KeyboardInterrupt:
        pass
    time.sleep(0.1)


if __name__ == "__main__":
    main()
