"""Recurring payments (subscriptions, bills, loan instalments). Pure pandas, no Django.

A merchant is recurring when it was paid at least `min_count` times at a regular interval:
most gaps between payments lie within ±35 % of the median gap, and that median matches a
known cadence. Amounts may vary (electricity) — `fixed_amount` says whether they do.
"""

import pandas as pd

from .monthly import flow

CADENCES = {  # name: (min days, max days) for the median gap
    "weekly": (5, 9),
    "monthly": (25, 36),
    "quarterly": (80, 100),
    "yearly": (350, 380),
}
DAYS_PER_MONTH = 365.25 / 12
# Calendar steps, so a payment on the 21st is next expected on the 21st.
STEP = {
    "weekly": pd.Timedelta(days=7),
    "monthly": pd.DateOffset(months=1),
    "quarterly": pd.DateOffset(months=3),
    "yearly": pd.DateOffset(years=1),
}


def _cadence(gap: float) -> str | None:
    return next((name for name, (lo, hi) in CADENCES.items() if lo <= gap <= hi), None)


def find_recurring(
    df: pd.DataFrame, *, min_count: int = 3, regular_share: float = 0.7, price_change: float = 5.0
) -> pd.DataFrame:
    """One row per recurring merchant, largest monthly cost first.

    Columns: name (merchant, plus the amount level when one merchant has several), merchant,
    category, group, cadence, count, amount (median of the last 3 payments, positive),
    monthly_cost, first, last, next_expected, active (paid within 1.5 gaps of the data's last
    day), price_change (% last payment vs. median of earlier ones; NaN when the
    change is under `price_change` %).
    """
    columns = [
        "name", "merchant", "category", "group", "cadence", "count", "amount", "monthly_cost",
        "first", "last", "next_expected", "active", "price_change",
    ]  # fmt: skip
    out = df[(df["amount"] < 0) & (flow(df) == "spending") & df["merchant"].fillna("").ne("")]
    if out.empty:
        return _typed(pd.DataFrame(columns=columns))
    end = df["date"].max()
    rows = []
    for merchant, g in out.sort_values("date").groupby("merchant"):
        # Several charges on one day (split payments) count as one payment.
        daily = g.groupby("date")["amount"].sum().abs()
        found = _check(daily, min_count, regular_share)
        if found:
            parts = [(merchant, daily, found)]
        else:
            # Two loans or subscriptions at one merchant: test each amount level on its own.
            parts = []
            for level in _amount_levels(g):
                part = g.loc[level].groupby("date")["amount"].sum().abs()
                hit = _check(part, min_count, regular_share)
                if hit:
                    parts.append(
                        (f"{merchant} (≈{part.median():,.0f})".replace(",", " "), part, hit)
                    )
        for name, series, (cadence, median_gap) in parts:
            rows.append(_row(name, merchant, g, series, cadence, median_gap, end, price_change))
    result = _typed(pd.DataFrame(rows, columns=columns))
    return result.sort_values("monthly_cost", ascending=False, ignore_index=True)


def _typed(result: pd.DataFrame) -> pd.DataFrame:
    # An empty frame has object columns; a boolean mask on one would select columns instead.
    return result.astype({"active": bool, "amount": float, "monthly_cost": float})


def _check(daily: pd.Series, min_count: int, regular_share: float):
    """(cadence, median gap) when the payment dates are regular, else None."""
    if len(daily) < min_count:
        return None
    gaps = daily.index.to_series().diff().dt.days.dropna()
    median_gap = gaps.median()
    cadence = _cadence(median_gap)
    if cadence is None or ((gaps - median_gap).abs() <= 0.35 * median_gap).mean() < regular_share:
        return None
    return cadence, median_gap


def _amount_levels(g: pd.DataFrame, tolerance: float = 0.15) -> list[pd.Index]:
    """Group a merchant's rows into amount levels: a new level starts when an amount is more
    than `tolerance` above the level's first amount."""
    amounts = g["amount"].abs().sort_values()
    levels, current, base = [], [], None
    for idx, value in amounts.items():
        if base is not None and value > base * (1 + tolerance):
            levels.append(pd.Index(current))
            current, base = [], None
        if base is None:
            base = value
        current.append(idx)
    if current:
        levels.append(pd.Index(current))
    return levels


def _row(name, merchant, g, daily, cadence, median_gap, end, price_change):
    amount = daily.tail(3).median()
    earlier = daily.iloc[:-1].median()
    change = (daily.iloc[-1] - earlier) / earlier * 100 if earlier else float("nan")
    last = daily.index[-1]
    return {
        "name": name,
        "merchant": merchant,
        "category": g["category"].mode().iat[0] if g["category"].notna().any() else None,
        "group": g["group"].mode().iat[0] if g["group"].notna().any() else None,
        "cadence": cadence,
        "count": len(daily),
        "amount": round(amount, 2),
        "monthly_cost": round(amount * DAYS_PER_MONTH / median_gap, 2),
        "first": daily.index[0],
        "last": last,
        "next_expected": last + STEP.get(cadence, pd.Timedelta(days=round(median_gap))),
        "active": (end - last).days <= 1.5 * median_gap,
        "price_change": round(change, 1) if abs(change) >= price_change else float("nan"),
    }
