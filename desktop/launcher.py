"""Aurora as a desktop app: start a local server and show it in its own window.

Everything stays on this computer. The data folder is the user's own (override with
AURORA_DATA_DIR):
- macOS: ~/Library/Application Support/Aurora
- Windows: %APPDATA%\\Aurora
- Linux: ~/.local/share/aurora

The server listens on 127.0.0.1 only, so nothing else on the network can reach it. The
window is the system's own web view (pywebview: WebKit on macOS, Edge WebView2 on Windows).
Without pywebview, for example from source, Aurora opens in the browser instead. Run from
source with `python desktop/launcher.py`, or as the packaged app (`make app`).

AURORA_NO_BROWSER=1 starts only the server (the CI smoke test). AURORA_CHECK_WINDOW=1 loads
the window toolkit and exits, so CI can check the packaged app contains it.
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

# Shown in the window while the first page loads (pandas and every view, a few seconds).
LOADING = """<!doctype html><meta charset="utf-8"><style>
:root { color-scheme: light dark; font: 16px system-ui, sans-serif; }
body { display: grid; place-items: center; height: 90vh; margin: 0; color: #6b7280; }
</style><p>Starting Aurora…</p>"""


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


def warm_up(url: str) -> None:
    """Load the first page once (it imports pandas and every view), so the user never waits
    on a blank page."""
    from urllib.request import urlopen

    for _ in range(120):
        try:
            with urlopen(url, timeout=60):
                return
        except OSError:
            time.sleep(0.5)


def toolkit():
    """pywebview with the platform's own web view loaded, or None if it is not available."""
    try:
        import webview

        if sys.platform == "darwin":
            import webview.platforms.cocoa  # noqa: F401
        elif sys.platform == "win32":
            import webview.platforms.edgechromium  # noqa: F401
            import webview.platforms.winforms  # noqa: F401
    except Exception:  # not installed, or no web view on this system
        return None
    return webview


def show_window(url: str, folder: Path, wait=None) -> bool:
    """Show Aurora in its own window until the user closes it. With `wait`, the window opens
    at once with a loading text and switches to `url` when `wait(url)` returns. False when
    there is no window toolkit: the caller opens the browser instead."""
    webview = toolkit()
    if webview is None:
        return False
    webview.settings["ALLOW_DOWNLOADS"] = True  # the backup download
    webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True
    window = webview.create_window(
        "Aurora", url=None if wait else url, html=LOADING if wait else None,
        width=1280, height=860, min_size=(420, 560), text_select=True, zoomable=True,
    )  # fmt: skip

    def load():
        if wait:
            wait(url)
            window.load_url(url)

    try:
        # Not private: the window keeps its cookies and stored choices between starts.
        # Edge WebView2 only on Windows: never the old Internet Explorer engine.
        gui = "edgechromium" if sys.platform == "win32" else None
        webview.start(load, gui=gui, private_mode=False, storage_path=str(folder / "window"))
    except Exception as exc:  # e.g. Edge WebView2 missing on an old Windows
        print(f"Could not open a window ({exc}); using the browser.")
        return False
    return True


def log_to_file(folder: Path) -> None:
    """A windowed program has no console: keep its output in the data folder."""
    if sys.stdout is None or sys.stderr is None:
        log = open(folder / "aurora.log", "a", buffering=1, encoding="utf-8")  # noqa: SIM115
        sys.stdout = sys.stdout or log
        sys.stderr = sys.stderr or log


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
    if os.environ.get("AURORA_CHECK_WINDOW"):
        raise SystemExit(0 if toolkit() else 1)
    folder = data_dir()
    folder.mkdir(parents=True, exist_ok=True)
    log_to_file(folder)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)  # the packaged app writes to a pipe
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    sys.path.insert(0, str(root))
    url = running()
    if url:
        print(f"Aurora is already running: {url}")
        if not show_window(url, folder):
            webbrowser.open(url)
        return
    configure(folder)
    print(f"Aurora: data in {folder}")
    prepare()

    from waitress import serve

    from config.wsgi import application

    port = free_port()
    url = f"http://{HOST}:{port}/"
    server = threading.Thread(
        target=serve, args=[application],
        kwargs={"host": HOST, "port": port, "threads": 4, "channel_timeout": 900},
        daemon=True,
    )  # fmt: skip
    server.start()
    print(f"Aurora is running at {url}")
    try:
        if os.environ.get("AURORA_NO_BROWSER"):
            server.join()
        elif show_window(url, folder, wait=warm_up):
            pass  # the window was closed: stop
        else:
            warm_up(url)
            webbrowser.open(url)
            print("Close this window or press Ctrl+C to stop.")
            server.join()
    except KeyboardInterrupt:
        pass
    # The server thread never returns on its own; the database is saved after every request.
    os._exit(0)


if __name__ == "__main__":
    main()
