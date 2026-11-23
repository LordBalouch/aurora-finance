"""ORM -> pandas. The only place analysis code touches the database."""

import pandas as pd

from .models import Transaction

COLUMNS = {
    "id": "id",
    "date": "date",
    "account": "account__name",
    "amount": "amount",
    "description": "description_clean",
    "merchant": "merchant",
    "category": "category__name",
    "group": "category__parent__name",
    "category_id": "category_id",
    "group_id": "category__parent_id",
    "kind": "category__kind",
}


def transactions_df(*, accounts=None, start=None, end=None) -> pd.DataFrame:
    """All transactions as a typed DataFrame, oldest first. `end` is inclusive.

    Amounts become float here: analysis sums and averages, and results are rounded to øre.
    Stored amounts stay Decimal.
    """
    qs = Transaction.objects.all()
    if accounts:
        qs = qs.filter(account__name__in=accounts)
    if start:
        qs = qs.filter(date__gte=start)
    if end:
        qs = qs.filter(date__lte=end)
    rows = qs.order_by("date", "id").values_list(*COLUMNS.values())
    df = pd.DataFrame.from_records(list(rows), columns=list(COLUMNS))
    df["date"] = pd.to_datetime(df["date"])
    df["amount"] = df["amount"].astype(float)
    return df
