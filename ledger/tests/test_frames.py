from datetime import date

import pytest

from ledger.frames import transactions_df
from ledger.models import Account, Category

pytestmark = pytest.mark.django_db


def test_transactions_df_is_typed_and_filtered(add_transactions):
    acc = Account.objects.create(name="Everyday")
    food = Category.objects.create(name="Food", kind="variable")
    groceries = Category.objects.create(name="Groceries", parent=food, kind="variable")
    add_transactions(
        acc, [(date(2026, 1, 3), "-12.50", groceries), (date(2026, 2, 1), "100.00", None)]
    )
    df = transactions_df()
    assert list(df["amount"]) == [-12.5, 100.0]
    assert str(df["date"].dtype).startswith("datetime64")
    assert df.iloc[0][["category", "group", "kind"]].tolist() == ["Groceries", "Food", "variable"]
    assert len(transactions_df(start=date(2026, 2, 1))) == 1
    assert transactions_df(accounts=["Nope"]).empty
