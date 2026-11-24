"""Read-only tools for "Ask your data".

The model answers a question by calling these, never by writing SQL or doing its own maths.
Each tool runs one `insights` function on the transactions and returns a small dict (whole
kroner, at most ~50 rows) plus an optional chart spec for the page. Bad arguments raise
`ToolError`, whose message goes back to the model so it can try again.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date

import pandas as pd

from insights.anomalies import group_anomalies
from insights.budget import progress
from insights.counterparties import top_merchants as _top_merchants
from insights.debt import plan
from insights.monthly import complete_months, flow, monthly_summary
from insights.recurring import find_recurring
from insights.trends import monthly_by_group
from ledger.frames import transactions_df
from ledger.models import Budget
from web.charts import chart


class ToolError(ValueError):
    """A bad argument. The message is meant for the model."""


def _r(value):
    return None if value is None or pd.isna(value) else round(float(value))


@dataclass
class Data:
    """The transactions for one question, loaded once and shared by every tool call."""

    today: date = field(default_factory=date.today)
    _df: pd.DataFrame | None = None

    @property
    def df(self) -> pd.DataFrame:
        if self._df is None:
            self._df = transactions_df()
        return self._df

    @property
    def months(self) -> pd.PeriodIndex:
        """Complete months with data, oldest first."""
        return complete_months(monthly_summary(self.df), self.today).index

    def groups(self) -> dict[str, list[str]]:
        """Category group -> its categories, as used in the data."""
        rows = self.df.dropna(subset=["group"])
        return {g: sorted(rows.loc[rows["group"] == g, "category"].unique()) for g in
                sorted(rows["group"].unique())}  # fmt: skip

    def context(self) -> dict:
        """What the model needs to choose arguments: dates, groups and categories."""
        df = self.df
        if df.empty:
            return {"today": str(self.today), "data": "no transactions yet"}
        months = self.months
        return {
            "today": str(self.today),
            "first_date": str(df["date"].min().date()),
            "last_date": str(df["date"].max().date()),
            "last_complete_month": str(months[-1]) if len(months) else None,
            "accounts": sorted(df["account"].unique()),
            "groups_and_categories": self.groups(),
        }


# --- argument checks ---------------------------------------------------------------------


def _month(value, name: str) -> pd.Period:
    try:
        return pd.Period(str(value), freq="M")
    except (ValueError, TypeError):
        raise ToolError(f"{name} must be a month like 2026-03, got {value!r}.") from None


def _range(data: Data, args: dict, default_months: int = 12, prefix: str = "") -> pd.PeriodIndex:
    """from/to (inclusive months). Defaults to the last `default_months` complete months."""
    complete = data.months
    if not len(complete):
        raise ToolError("There is no complete month of data yet.")
    end = _month(args[prefix + "to"], prefix + "to") if args.get(prefix + "to") else complete[-1]
    if args.get(prefix + "from"):
        start = _month(args[prefix + "from"], prefix + "from")
    else:
        start = end - (default_months - 1)
    if start > end:
        raise ToolError(f"{prefix}from ({start}) is after {prefix}to ({end}).")
    first = data.df["date"].min().to_period("M")
    last = data.df["date"].max().to_period("M")
    if end < first or start > last:
        raise ToolError(f"No data in {start} to {end}. Data runs from {first} to {last}.")
    return pd.period_range(max(start, first), min(end, last), freq="M")


def _pick(value, names, what: str) -> str | None:
    """Case-insensitive match of a group or category name."""
    if not value:
        return None
    lookup = {n.lower(): n for n in names}
    found = lookup.get(str(value).strip().lower())
    if found is None:
        raise ToolError(f"Unknown {what} {value!r}. Use one of: {', '.join(sorted(names))}.")
    return found


def _spending_rows(data: Data, months: pd.PeriodIndex, group=None, category=None):
    df = data.df
    rows = df[flow(df) == "spending"]
    rows = rows.assign(month=rows["date"].dt.to_period("M"), spent=-rows["amount"])
    rows = rows[rows["month"].isin(months)]
    groups = data.groups()
    group = _pick(group, groups, "group")
    category = _pick(category, sorted({c for cs in groups.values() for c in cs}), "category")
    if group:
        rows = rows[rows["group"] == group]
    if category:
        rows = rows[rows["category"] == category]
    return rows, group, category


# --- tools -------------------------------------------------------------------------------

MONTH = {"type": "string", "description": "Month as YYYY-MM"}
GROUP = {"type": "string", "description": "A category group name, see groups_and_categories"}
CATEGORY = {"type": "string", "description": "A category name, see groups_and_categories"}


def monthly_overview(data: Data, args: dict):
    months = _range(data, args)
    s = monthly_summary(data.df).reindex(months)
    rows = [
        {"month": str(m), "income": _r(r["income"]), "spending": _r(r["spending"]),
         "net": _r(r["net"])}
        for m, r in s.iterrows()
    ]  # fmt: skip
    result = {
        "months": rows,
        "total": {k: _r(s[k].sum()) for k in ("income", "spending", "net")},
        "average_per_month": {k: _r(s[k].mean()) for k in ("income", "spending", "net")},
    }
    x = [str(m) for m in months]
    spec = chart("bar", x, {"Income": list(s["income"]), "Spending": list(s["spending"])})
    return result, spec


def spending(data: Data, args: dict):
    months = _range(data, args)
    rows, group, category = _spending_rows(data, months, args.get("group"), args.get("category"))
    per_month = rows.groupby("month")["spent"].sum().reindex(months, fill_value=0.0)
    result = {
        "from": str(months[0]),
        "to": str(months[-1]),
        "group": group,
        "category": category,
        "total": _r(per_month.sum()),
        "average_per_month": _r(per_month.mean()),
        "transactions": int(len(rows)),
        "per_month": {str(m): _r(v) for m, v in per_month.items()},
    }
    if not group and not category:
        # One call answers "where did the money go": the split per group, largest first.
        groups = rows.groupby(rows["group"].fillna("Uncategorized"))["spent"].sum()
        groups = groups[groups > 0].sort_values(ascending=False)
        result["per_group"] = {g: _r(v) for g, v in groups.items()}
        top = groups.head(8).iloc[::-1]
        spec = chart("bar", list(top.index), {"Spent": list(top)}, horizontal=True)
        return result, spec
    label = category or group
    return result, chart("bar", [str(m) for m in months], {label: list(per_month)})


def compare_periods(data: Data, args: dict):
    a = _range(data, args, prefix="a_")
    b = _range(data, args, prefix="b_")
    spend_a = _spending_rows(data, a)[0].groupby("group", dropna=False)["spent"].sum()
    spend_b = _spending_rows(data, b)[0].groupby("group", dropna=False)["spent"].sum()
    table = pd.DataFrame({"a": spend_a, "b": spend_b}).fillna(0.0)
    table.index = table.index.fillna("Uncategorized")
    table = table[(table["a"] > 0) | (table["b"] > 0)]
    table = table.sort_values("b", ascending=False)
    groups = {
        g: {"a": _r(r["a"]), "b": _r(r["b"]), "change": _r(r["b"] - r["a"]),
            "change_percent": _r((r["b"] - r["a"]) / r["a"] * 100) if r["a"] > 0 else None}
        for g, r in table.iterrows()
    }  # fmt: skip
    result = {
        "a": f"{a[0]} to {a[-1]} ({len(a)} months)",
        "b": f"{b[0]} to {b[-1]} ({len(b)} months)",
        "total": {
            "a": _r(table["a"].sum()),
            "b": _r(table["b"].sum()),
            "change": _r(table["b"].sum() - table["a"].sum()),
        },  # fmt: skip
        "per_group": groups,
    }
    top = table.head(8)
    names = (f"{a[0]}–{a[-1]}", f"{b[0]}–{b[-1]}")  # short, so the legend fits on a phone
    spec = chart("bar", list(top.index), {names[0]: list(top["a"]), names[1]: list(top["b"])})
    return result, spec


def top_merchants(data: Data, args: dict):
    months = _range(data, args)
    n = max(1, min(int(args.get("n") or 10), 25))
    rows, group, _ = _spending_rows(data, months, args.get("group"))
    window = data.df.loc[rows.index]
    table = _top_merchants(window, n=n)
    result = {
        "from": str(months[0]),
        "to": str(months[-1]),
        "group": group,
        "merchants": [
            {
                "merchant": r["merchant"],
                "group": r["group"],
                "count": int(r["count"]),
                "total": _r(r["total"]),
                "share_percent": _r(r["share"]),
            }
            for _, r in table.iterrows()
        ],  # fmt: skip
    }
    top = table.head(8).iloc[::-1]
    spec = chart("bar", list(top["merchant"]), {"Spent": list(top["total"])}, horizontal=True)
    return result, spec if len(top) else None


def recurring_payments(data: Data, args: dict):
    r = find_recurring(data.df)
    active = r[r["active"]].sort_values("monthly_cost", ascending=False)
    result = {
        "total_per_month": _r(active["monthly_cost"].sum()),
        "payments": [
            {
                "name": p["name"],
                "category": p["category"],
                "every": p["cadence"],
                "amount": _r(p["amount"]),
                "per_month": _r(p["monthly_cost"]),
                "last_paid": str(p["last"].date()),
                "price_change_percent": _r(p["price_change"]),
            }
            for _, p in active.head(40).iterrows()
        ],  # fmt: skip
    }
    top = active.head(8).iloc[::-1]
    spec = chart("bar", list(top["name"]), {"Per month": list(top["monthly_cost"])},
                 horizontal=True)  # fmt: skip
    return result, spec if len(top) else None


def unusual_months(data: Data, args: dict):
    table = monthly_by_group(data.df, data.months, top=50)
    a = group_anomalies(table, last=int(args.get("last") or 3))
    return {
        "method": "robust z-score against the group's previous 12 months",
        "unusual": [
            {
                "month": str(x["month"]),
                "group": x["group"],
                "amount": _r(x["amount"]),
                "usual": _r(x["typical"]),
                "z": round(float(x["z"]), 1),
            }
            for _, x in a.iterrows()
        ],  # fmt: skip
    }, None


def _month_after(today: date, months: int | None) -> str | None:
    return None if months is None else str(pd.Period(today, "M") + months)


def _pace(result: dict, today: date) -> dict:
    """A payoff plan in words the model can repeat without doing date arithmetic."""
    return {
        "months_until_debt_free": result["months"],
        "debt_free_month": _month_after(today, result["months"]),
        "total_interest": _r(result["interest"]),
        "paid_off_month_per_loan": {
            name: _month_after(today, m) for name, m in result["paid_off"].items()
        },
    }


def debt_payoff(data: Data, args: dict):
    from web.wealth import current_loans  # web imports ai, so import here

    extra = float(args.get("extra_per_month") or 0)
    if extra < 0 or extra > 1_000_000:
        raise ToolError("extra_per_month must be between 0 and 1 000 000.")
    _, _, _, _, loans, aggregate = current_loans(data.df)
    if not loans:
        raise ToolError("No debt balances are registered (add them on the Debt page).")
    base, faster = plan(loans), plan(loans, extra=extra)
    result = {
        "loans": [
            {
                "name": loan["name"],
                "balance": _r(loan["balance"]),
                "rate_percent": loan["rate"],
                "payment_per_month": _r(loan["payment"]),
                "rate_is_estimate": loan.get("estimated_rate", False),
            }
            for loan in loans
        ],  # fmt: skip
        "one_aggregate_loan": aggregate,
        "current_pace": _pace(base, data.today),
    }
    series = {"Current pace": base["balances"]}
    if extra:
        result["with_extra"] = {"extra_per_month": _r(extra), **_pace(faster, data.today)}
        if base["months"] and faster["months"]:
            result["with_extra"]["months_saved"] = base["months"] - faster["months"]
            result["with_extra"]["interest_saved"] = _r(base["interest"] - faster["interest"])
        series[f"+{_r(extra)} kr/month"] = faster["balances"]
    length = max(len(v) for v in series.values())
    series = {k: v + [0] * (length - len(v)) for k, v in series.items()}
    x = [f"{m // 12}y {m % 12}m" if m % 12 else f"{m // 12}y" for m in range(length)]
    return result, chart("line", x, series)


def budget_status(data: Data, args: dict):
    df = data.df
    month = _month(args["month"], "month") if args.get("month") else pd.Period(data.today, "M")
    budgets = Budget.objects.filter(month=month.start_time.date()).select_related("category")
    planned = {b.category.name: float(b.amount) for b in budgets}
    if not planned:
        raise ToolError(f"No budget is set for {month}.")
    p = progress(df, planned, month, data.today, recurring=find_recurring(df))
    result = {
        "month": str(month),
        "groups": [
            {
                "group": r["group"],
                "budget": _r(r["budget"]),
                "spent": _r(r["spent"]),
                "forecast": _r(r["forecast"]),
                "status": r["status"],
            }
            for _, r in p.iterrows()
        ],  # fmt: skip
    }
    spec = chart("bar", list(p["group"]), {"Budget": list(p["budget"]), "Spent": list(p["spent"])})
    return result, spec


def find_transactions(data: Data, args: dict):
    text = str(args.get("text") or "").strip()
    if len(text) < 2:
        raise ToolError("text must be at least 2 characters.")
    df = data.df
    hits = df[df["description"].str.contains(text, case=False, regex=False, na=False)]
    if args.get("from") or args.get("to"):
        months = _range(data, args)
        hits = hits[hits["date"].dt.to_period("M").isin(months)]
    limit = max(1, min(int(args.get("limit") or 25), 25))
    newest = hits.sort_values("date", ascending=False)
    return {
        "matches": int(len(hits)),
        "money_in": _r(hits.loc[hits["amount"] > 0, "amount"].sum()),
        "money_out": _r(-hits.loc[hits["amount"] < 0, "amount"].sum()),
        "first": str(hits["date"].min().date()) if len(hits) else None,
        "last": str(hits["date"].max().date()) if len(hits) else None,
        "newest": [
            {
                "date": str(r["date"].date()),
                "amount": round(float(r["amount"]), 2),
                "text": r["description"],
                "category": r["category"],
            }
            for _, r in newest.head(limit).iterrows()
        ],  # fmt: skip
    }, None


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    properties: dict
    run: Callable
    required: tuple = ()

    def schema(self) -> dict:
        return {"type": "object", "properties": self.properties, "required": list(self.required)}


RANGE = {
    "from": {**MONTH, "description": "First month, YYYY-MM (default: 12 months before 'to')"},
    "to": {**MONTH, "description": "Last month, YYYY-MM (default: last complete month)"},
}

TOOLS = {
    t.name: t
    for t in [
        Tool("monthly_overview",
             "Income, spending and net per month for a range of months, with totals and "
             "averages. Transfers between own accounts and money between friends are excluded.",
             RANGE, monthly_overview),
        Tool("spending",
             "Total spending and spending per month, optionally for one group or category. "
             "Without a group or category it also returns the split per group. Not for one shop, "
             "service or person: use find_transactions for that.",
             {**RANGE, "group": GROUP, "category": CATEGORY}, spending),
        Tool("compare_periods",
             "Spending per group in period a (the earlier one) and period b (the later one), "
             "with the change from a to b. Use it for 'this summer vs last summer' or 'this "
             "year vs last year'.",
             {"a_from": MONTH, "a_to": MONTH, "b_from": MONTH, "b_to": MONTH},
             compare_periods, ("a_from", "a_to", "b_from", "b_to")),
        Tool("top_merchants",
             "Where the money went: merchants by amount spent, optionally within one group.",
             {**RANGE, "group": GROUP,
              "n": {"type": "integer", "description": "How many, 1-25 (default 10)"}},
             top_merchants),
        Tool("recurring_payments",
             "Active subscriptions, bills and loan payments: how often, cost per month and "
             "the latest price change. For bills that vary (electricity) a price change can "
             "just be the season.", {}, recurring_payments),
        Tool("unusual_months",
             "Months where a group's spending was far from its own normal (anomalies).",
             {"last": {"type": "integer", "description": "How many recent months to check "
                       "(default 3)"}},
             unusual_months),
        Tool("debt_payoff",
             "When the debt is paid off and the total interest, at the current pace and "
             "with an extra amount each month (extra goes to the highest rate first).",
             {"extra_per_month": {"type": "number", "description": "Extra kr per month"}},
             debt_payoff),
        Tool("budget_status",
             "This month's budget per group: budget, spent so far, forecast and status.",
             {"month": {**MONTH, "description": "YYYY-MM (default: this month)"}},
             budget_status),
        Tool("find_transactions",
             "Everything paid to or received from one shop, service or person (e.g. "
             "'Spotify', 'Rema'): searches the bank text, case-insensitive. Returns the "
             "number of matches, total money in and out, and the newest rows. Searches all "
             "dates unless from/to are given.",
             {**RANGE, "text": {"type": "string", "description": "Text to look for"},
              "limit": {"type": "integer", "description": "Rows to return, 1-25"}},
             find_transactions, ("text",)),
    ]
}  # fmt: skip


def run(data: Data, name: str, args: dict | None) -> tuple[dict, dict | None]:
    """Run one tool. Raises ToolError for an unknown tool or a bad argument."""
    tool = TOOLS.get(name)
    if tool is None:
        raise ToolError(f"Unknown tool {name!r}. Tools: {', '.join(TOOLS)}.")
    args = args if isinstance(args, dict) else {}
    missing = [k for k in tool.required if not args.get(k)]
    if missing:
        raise ToolError(f"Missing argument(s): {', '.join(missing)}.")
    try:
        return tool.run(data, args)
    except ToolError:
        raise
    except (ValueError, TypeError, KeyError) as exc:
        raise ToolError(f"Could not run {name}: {exc}") from exc
