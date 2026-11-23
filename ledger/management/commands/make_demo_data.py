from datetime import date
from decimal import Decimal

import pandas as pd
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction as db_transaction

from insights.budget import suggest
from ledger.categorize import merchant_key
from ledger.dedup import fingerprints
from ledger.demo import generate
from ledger.frames import transactions_df
from ledger.importers.base import ParsedRow
from ledger.models import (
    Account,
    Budget,
    Category,
    DebtBalance,
    Goal,
    ImportBatch,
    Rule,
    TaxYear,
    Transaction,
)
from ledger.normalize import clean_description
from ledger.services import apply_rules

# Rules a user would make in the app: the demo shows them next to the built-in ones.
USER_RULES = [
    ("HUSLEIE", "Rent & mortgage", "out"),
    ("LEKELAND", "Other shopping", "out"),
]


class Command(BaseCommand):
    help = (
        "Fill an EMPTY database with synthetic demo data (2 years, two accounts, tax years, "
        "loans, budget, goals). Use a separate file: DB_PATH=data/demo.sqlite3 (make demo)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--seed", type=int, default=7)
        parser.add_argument("--end", type=date.fromisoformat, default=None, help="YYYY-MM-DD")

    def handle(self, seed, end, **options):
        if Transaction.objects.exists():
            raise CommandError(
                "The database already has transactions. Demo data only goes into an empty "
                "database: run `make demo`, which uses data/demo.sqlite3."
            )
        end = end or date.today()
        call_command("seed_categories", stdout=self.stdout)
        with db_transaction.atomic():
            count = self._transactions(generate(end, seed=seed))
            self._extras(end)
        self.stdout.write(self.style.SUCCESS(f"Demo data: {count} transactions up to {end}."))

    def _transactions(self, rows) -> int:
        by_name = {c.name: c for c in Category.objects.exclude(parent=None)}
        for pattern, category, sign in USER_RULES:
            Rule.objects.get_or_create(
                pattern=pattern, match="word", sign=sign,
                defaults={"category": by_name[category], "source": "user"},
            )  # fmt: skip
        count = 0
        for name in sorted({r.account for r in rows}):
            account = Account.objects.create(name=name, bank="Demo Bank")
            mine = [r for r in rows if r.account == name]
            parsed = [ParsedRow(i, r.date, r.amount, r.description) for i, r in enumerate(mine)]
            batch = ImportBatch.objects.create(
                account=account, file_name=f"demo-{name.lower()}.csv", file_sha256="0" * 64,
                importer="demo", rows_total=len(mine), rows_imported=len(mine), rows_duplicate=0,
            )  # fmt: skip
            Transaction.objects.bulk_create(
                Transaction(
                    account=account,
                    import_batch=batch,
                    date=r.date,
                    amount=r.amount,
                    description_raw=r.description,
                    description_clean=clean_description(r.description),
                    merchant=merchant_key(clean_description(r.description)),
                    fingerprint=fp,
                )
                for r, fp in zip(mine, fingerprints(parsed), strict=True)
            )
            count += len(mine)
        apply_rules()
        return count

    def _extras(self, end: date):
        """Tax years, loans, this month's budget and two goals, so every page has content."""
        for n, y in enumerate((end.year - 2, end.year - 1)):
            scale = 1.035**n
            deposits, funds, debt = 38_000 + 24_000 * n, 24_000 * (n + 1), 512_400 - 43_500 * n
            TaxYear.objects.create(
                year=y, wages=round(462_000 * scale), interest_income=310,
                total_income=round(462_310 * scale), personal_income=round(462_000 * scale),
                interest_expense=round(debt * 0.052), total_deductions=48_200,
                general_income=round(462_310 * scale - 48_200),
                tax_assessed=round(118_500 * scale), tax_prepaid=round(123_400 * scale),
                settlement=4_870, bank_deposits=deposits, funds_and_shares=funds, debt=debt,
                net_wealth=deposits + funds - debt, notes="Synthetic demo figures.",
            )  # fmt: skip
        today = pd.Timestamp(end)
        for lender, balance, rate, payment, merchant in (
            ("Lånekassen (student loan)", 311_200, 4.7, 2_950, "lånekassen efaktura"),
            ("Santander (car loan)", 118_400, 8.9, 3_250, "santander consumer"),
        ):
            DebtBalance.objects.create(
                lender=lender, as_of=end, balance=Decimal(balance), annual_rate=Decimal(str(rate)),
                monthly_payment=Decimal(payment), merchant=merchant, source="statement",
            )  # fmt: skip
        groups = {c.name: c for c in Category.objects.filter(parent=None)}
        month = today.to_period("M")
        for name, amount in suggest(transactions_df(), month).items():
            if name in groups:
                Budget.objects.create(
                    month=month.start_time.date(), category=groups[name], amount=Decimal(amount)
                )
        Goal.objects.create(name="Buffer account", target_amount=Decimal(60_000),
                            saved=Decimal(22_500), monthly=Decimal(2_000))  # fmt: skip
        Goal.objects.create(name="Summer trip", target_amount=Decimal(18_000),
                            saved=Decimal(6_000), monthly=Decimal(1_500),
                            target_date=date(end.year + 1, 6, 15))  # fmt: skip
