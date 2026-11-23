"""Import workflow: preview a file, import it, undo an import."""

import hashlib
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from django.db import transaction as db_transaction

from .categorize import Matcher, RuleSpec, TxnView, merchant_key
from .dedup import fingerprints
from .importers import ParsedRow, detect, read_table
from .models import Account, ImportBatch, Rule, Transaction
from .normalize import clean_description


@dataclass
class Preview:
    importer: str
    rows: list[ParsedRow]
    new: list[tuple[ParsedRow, str]]  # (row, fingerprint) not yet in the account
    duplicates: int
    sha256: str
    already_imported: ImportBatch | None = None
    first: date | None = None
    last: date | None = None
    money_in: Decimal = Decimal(0)
    money_out: Decimal = Decimal(0)
    sample: list[ParsedRow] = field(default_factory=list)


def preview(data: bytes, account: Account | None) -> Preview:
    """Parse and compare with what the account already has. Writes nothing."""
    header, raw_rows = read_table(data)
    importer = detect(header)
    rows = importer.parse(header, raw_rows)
    prints = fingerprints(rows)
    existing = set()
    if account is not None:
        existing = set(
            Transaction.objects.filter(account=account, fingerprint__in=prints).values_list(
                "fingerprint", flat=True
            )
        )
    new = [(r, fp) for r, fp in zip(rows, prints, strict=True) if fp not in existing]
    sha = hashlib.sha256(data).hexdigest()
    dates = [r.date for r in rows]
    return Preview(
        importer=importer.name,
        rows=rows,
        new=new,
        duplicates=len(rows) - len(new),
        sha256=sha,
        already_imported=(
            ImportBatch.objects.filter(account=account, file_sha256=sha).first()
            if account
            else None
        ),
        first=min(dates) if dates else None,
        last=max(dates) if dates else None,
        money_in=sum((r.amount for r in rows if r.amount > 0), Decimal(0)),
        money_out=sum((r.amount for r in rows if r.amount < 0), Decimal(0)),
        sample=sorted(rows, key=lambda r: r.date, reverse=True)[:20],
    )


@db_transaction.atomic
def import_file(data: bytes, file_name: str, account: Account) -> ImportBatch:
    result = preview(data, account)
    batch = ImportBatch.objects.create(
        account=account,
        file_name=file_name[:255],
        file_sha256=result.sha256,
        importer=result.importer,
        rows_total=len(result.rows),
        rows_imported=len(result.new),
        rows_duplicate=result.duplicates,
    )
    Transaction.objects.bulk_create(
        Transaction(
            account=account,
            import_batch=batch,
            date=row.date,
            amount=row.amount,
            description_raw=row.description[:500],
            description_clean=clean_description(row.description)[:500],
            balance=row.balance,
            merchant=merchant_key(clean_description(row.description)),
            fingerprint=fp,
        )
        for row, fp in result.new
    )
    apply_rules(batch.transactions.all())
    return batch


def undo_import(batch: ImportBatch) -> int:
    """Remove a batch and the transactions it added. Returns how many were removed."""
    count = batch.transactions.count()
    batch.delete()
    return count


def matcher() -> Matcher:
    return Matcher(
        RuleSpec(r.id, r.pattern, r.match, r.sign, r.priority, r.category_id)
        for r in Rule.objects.all()
    )


@db_transaction.atomic
def apply_rules(transactions=None) -> dict:
    """(Re)categorize transactions by rule. Hand-set categories are never touched."""
    qs = Transaction.objects.all() if transactions is None else transactions
    m = matcher()
    changed = []
    for t in qs.filter(category_locked=False).only(
        "id", "description_raw", "description_clean", "merchant", "amount", "category", "rule"
    ):
        filled = not t.merchant
        if filled:
            t.merchant = merchant_key(t.description_clean)
        hit = m.match(TxnView(t.description_raw, t.merchant, t.amount))
        new_cat, new_rule = (hit.category_id, hit.id) if hit else (None, None)
        if (t.category_id, t.rule_id) != (new_cat, new_rule) or filled:
            t.category_id, t.rule_id = new_cat, new_rule
            changed.append(t)
    Transaction.objects.bulk_update(changed, ["merchant", "category", "rule"], batch_size=500)
    total = qs.count()
    return {
        "changed": len(changed),
        "total": total,
        "categorized": qs.filter(category__isnull=False).count(),
    }
