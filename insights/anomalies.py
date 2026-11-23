"""Unusual months per category group. Pure pandas, no Django.

A month is unusual when it is far from the group's own history: robust z-score
(x - median) / (1.4826 · MAD) over up to `window` earlier months. MAD is used instead of the
standard deviation so one earlier spike does not hide the next one.
"""

import pandas as pd

MAD_SCALE = 1.4826  # makes MAD comparable to a standard deviation for normal data


def group_anomalies(
    table: pd.DataFrame,
    *,
    last: int = 3,
    window: int = 12,
    threshold: float = 3.0,
    min_history: int = 4,
    min_amount: float = 500.0,
) -> pd.DataFrame:
    """Unusual (month, group) cells among the last `last` months of `table` (rows = months,
    columns = groups, values = spending, e.g. from `trends.monthly_by_group`).

    Returns month, group, amount, typical (median of earlier months), difference, change (%),
    z (robust z-score), largest |z| first. A cell needs `min_history` earlier months and must
    differ from typical by at least `min_amount` kr.
    """
    columns = ["month", "group", "amount", "typical", "difference", "change", "z"]
    rows = []
    for pos in range(max(len(table) - last, 0), len(table)):
        history = table.iloc[max(pos - window, 0) : pos]
        if len(history) < min_history:
            continue
        median = history.median()
        mad = (history - median).abs().median() * MAD_SCALE
        # A flat history (MAD 0) would make every change infinite: use 10 % of the median.
        spread = mad.where(mad > 0, median.abs() * 0.1).replace(0, float("nan"))
        current = table.iloc[pos]
        z = (current - median) / spread
        for group in table.columns:
            diff = current[group] - median[group]
            if pd.notna(z[group]) and abs(z[group]) >= threshold and abs(diff) >= min_amount:
                rows.append(
                    {
                        "month": table.index[pos],
                        "group": group,
                        "amount": round(current[group], 2),
                        "typical": round(median[group], 2),
                        "difference": round(diff, 2),
                        "change": round(diff / median[group] * 100, 1) if median[group] else None,
                        "z": round(z[group], 1),
                    }
                )
    result = pd.DataFrame(rows, columns=columns)
    return result.reindex(result["z"].abs().sort_values(ascending=False).index).reset_index(
        drop=True
    )
