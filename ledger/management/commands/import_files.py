from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from ledger.importers import ImportFileError
from ledger.models import Account
from ledger.services import import_file


class Command(BaseCommand):
    help = (
        "Import bank exports (CSV/XLSX) into one account. Safe to re-run: duplicates are skipped."
    )

    def add_arguments(self, parser):
        parser.add_argument("files", nargs="+", type=Path)
        parser.add_argument("--account", required=True, help="Account name (created if missing)")
        parser.add_argument("--bank", default="")
        parser.add_argument("--number", default="", help="Account number (stored locally only)")

    def handle(self, files, account, bank, number, **options):
        acct, _ = Account.objects.get_or_create(
            name=account, defaults={"bank": bank, "account_number": number}
        )
        new = dup = 0
        for path in sorted(files):
            if not path.is_file():
                raise CommandError(f"Not a file: {path}")
            try:
                batch = import_file(path.read_bytes(), path.name, acct)
            except ImportFileError as exc:
                self.stderr.write(f"{path.name}: {exc}")
                continue
            new, dup = new + batch.rows_imported, dup + batch.rows_duplicate
            self.stdout.write(
                f"{path.name:30} new {batch.rows_imported:4}  skipped {batch.rows_duplicate:4}"
            )
        total = acct.transactions.count()
        self.stdout.write(
            self.style.SUCCESS(f"{acct.name}: +{new} new, {dup} skipped, {total} in total")
        )
