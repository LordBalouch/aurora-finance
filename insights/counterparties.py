"""Who the money goes to, and the flow from money in to spending. Pure pandas, no Django."""

import pandas as pd

from .monthly import flow


def top_merchants(df: pd.DataFrame, n: int = 15) -> pd.DataFrame:
    """Merchants by net spending: merchant, group, count, total, average, share (% of all
    spending). Largest first."""
    rows = df[(flow(df) == "spending") & df["merchant"].fillna("").ne("")]
    if rows.empty:
        return pd.DataFrame(columns=["merchant", "group", "count", "total", "average", "share"])
    spent = -rows["amount"]
    table = (
        rows.assign(spent=spent)
        .groupby("merchant")
        .agg(
            group=("group", lambda g: g.mode().iat[0] if g.notna().any() else None),
            count=("spent", "size"),
            total=("spent", "sum"),
        )
    )
    table["average"] = table["total"] / table["count"]
    table["share"] = table["total"] / spent.sum() * 100
    table = table[table["total"] > 0].sort_values("total", ascending=False).head(n)
    return table.reset_index().round(2)


def money_flow(df: pd.DataFrame) -> tuple[dict[str, float], dict[str, float]]:
    """Sources and uses of money for a Sankey: ({source: kr}, {use: kr}), both summing to the
    same total. Sources are income categories plus, when spending is larger, the net money in
    from friends & family and own accounts, then any remaining 'Shortfall'. Uses are spending
    groups plus 'Left over' when money in is larger."""
    kinds = flow(df)
    income = df[kinds == "income"].groupby(df["category"].fillna("Other income"))["amount"].sum()
    spent = -df[kinds == "spending"].groupby(df["group"].fillna("Uncategorized"))["amount"].sum()
    sources = {k: float(v) for k, v in income[income > 0].sort_values(ascending=False).items()}
    uses = {k: float(v) for k, v in spent[spent > 0].sort_values(ascending=False).items()}
    gap = sum(uses.values()) - sum(sources.values())
    extra = {
        "Friends & family (net)": df.loc[kinds == "netted", "amount"].sum(),
        "From own accounts (net)": df.loc[kinds == "transfer", "amount"].sum(),
    }
    for name, value in extra.items():
        if gap > 0 and value > 0:
            take = min(value, gap)
            sources[name] = float(take)
            gap -= take
    if gap > 0:
        sources["Shortfall"] = float(gap)
    elif gap < 0:
        uses["Left over"] = float(-gap)
    return {k: round(v, 2) for k, v in sources.items()}, {k: round(v, 2) for k, v in uses.items()}
