"""Back up and restore the whole database as one SQLite file.

The settings file (AI keys) is never part of a backup. A restore first copies the current
database to `data/backups/`, so it can always be undone by hand.
"""

import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.db import connection

REQUIRED_TABLES = {"ledger_transaction", "ledger_category", "django_migrations"}


class RestoreError(ValueError):
    """The file is not an Aurora backup. The message is safe to show."""


def _live() -> sqlite3.Connection:
    connection.ensure_connection()
    return connection.connection


def backup_file() -> Path:
    """A consistent copy of the live database in a temporary file (the caller deletes it)."""
    handle, name = tempfile.mkstemp(suffix=".sqlite3")
    Path(name).unlink()  # sqlite creates it
    target = sqlite3.connect(name)
    try:
        _live().backup(target)
    finally:
        target.close()
    return Path(name)


def check(path: Path) -> dict:
    """Open `path` read-only and check it looks like an Aurora database."""
    try:
        db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            tables = {r[0] for r in db.execute("select name from sqlite_master where type='table'")}
            if not REQUIRED_TABLES <= tables:
                raise RestoreError("This is not an Aurora backup: the expected tables are missing.")
            if db.execute("pragma integrity_check").fetchone()[0] != "ok":
                raise RestoreError("The backup file is damaged (integrity check failed).")
            return {
                "transactions": db.execute("select count(*) from ledger_transaction").fetchone()[0]
            }
        finally:
            db.close()
    except sqlite3.DatabaseError as exc:
        raise RestoreError("This is not a SQLite database file.") from exc


def safety_copy() -> Path | None:
    """Copy the current database to data/backups/ before it is replaced."""
    folder = Path(settings.DATA_DIR) / "backups"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"before-restore-{datetime.now():%Y%m%d-%H%M%S}.sqlite3"
    db = sqlite3.connect(target)
    try:
        _live().backup(db)
    finally:
        db.close()
    return target


def restore(path: Path) -> dict:
    """Replace the live database with the backup at `path`, then bring it up to date."""
    info = check(path)
    saved = safety_copy()
    source = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        source.backup(_live())
    finally:
        source.close()
    call_command("migrate", verbosity=0)
    return {**info, "safety_copy": saved}
