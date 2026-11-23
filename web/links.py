"""Drill-down links from charts and tables to the transactions page."""

from urllib.parse import urlencode

import pandas as pd
from django.urls import reverse


def transactions_url(**params) -> str:
    """Link to the transactions page with filters (drill-down)."""
    clean = {k: v for k, v in params.items() if v not in (None, "")}
    return f"{reverse('web:transactions')}?{urlencode(clean)}"


def month_range(month: pd.Period) -> dict:
    return {"from": month.start_time.date().isoformat(), "to": month.end_time.date().isoformat()}


def group_ids(df: pd.DataFrame) -> dict:
    ids = df.dropna(subset=["group_id"]).drop_duplicates("group")
    return {g: int(i) for g, i in zip(ids["group"], ids["group_id"], strict=True)}
