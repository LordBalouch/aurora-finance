"""Year figures from tax settlements, and loan payoff maths. Pure pandas/Python, no Django."""

import math

import pandas as pd

from .monthly import flow

MAX_MONTHS = 600  # 50 years: anything longer counts as "never paid off"


def years_table(rows: list[dict]) -> pd.DataFrame:
    """One row per tax year with the entered figures plus derived ones:

    - effective_rate: interest paid / average of debt at the start and end of the year (%)
    - interest_share: interest paid as % of income (business profit + wages + benefits)
    - tax_rate: assessed tax as % of total income
    - debt_change, net_wealth_change, deposits_change: against the year before
    """
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows).set_index("year").sort_index()
    df = df.drop(columns=[c for c in ("id", "settled_on", "notes") if c in df]).astype(float)
    earned = df[["business_profit", "wages", "benefits"]].fillna(0).sum(axis=1)
    debt_start = df["debt"].shift(1)
    average_debt = ((debt_start + df["debt"]) / 2).fillna(df["debt"])
    df["effective_rate"] = df["interest_expense"] / average_debt * 100
    df["interest_share"] = df["interest_expense"] / earned.where(earned > 0) * 100
    df["tax_rate"] = df["tax_assessed"] / df["total_income"].where(df["total_income"] > 0) * 100
    for column in ("debt", "net_wealth", "bank_deposits"):
        name = "deposits_change" if column == "bank_deposits" else f"{column}_change"
        df[name] = df[column].diff()
    return df.round(2)


def payoff(balance: float, annual_rate: float, payment: float) -> dict:
    """Month-by-month payoff of one loan with a fixed monthly payment.

    Returns months (None when the payment never covers the interest or it takes over
    MAX_MONTHS) and interest (total interest paid until then).
    """
    monthly_rate = annual_rate / 100 / 12
    if balance <= 0:
        return {"months": 0, "interest": 0.0}
    if payment <= balance * monthly_rate:
        return {"months": None, "interest": None}
    interest_total, months = 0.0, 0
    while balance > 0.005 and months < MAX_MONTHS:
        interest = balance * monthly_rate
        interest_total += interest
        balance = balance + interest - payment
        months += 1
    if months >= MAX_MONTHS:
        return {"months": None, "interest": None}
    return {"months": months, "interest": round(interest_total + min(balance, 0), 2)}


def months_closed_form(balance: float, annual_rate: float, payment: float) -> float | None:
    """n = -ln(1 - r·B/P) / ln(1 + r): the annuity formula, used to check `payoff`."""
    r = annual_rate / 100 / 12
    if r == 0:
        return balance / payment
    if payment <= balance * r:
        return None
    return -math.log(1 - r * balance / payment) / math.log(1 + r)


def plan(loans: list[dict], extra: float = 0.0) -> dict:
    """All loans paid together. Each loan: name, balance, rate (% per year), payment.

    `extra` kr per month goes to the loan with the highest rate (avalanche); when a loan is
    paid off, its payment moves to the next one. Returns months until debt-free, total
    interest, the month each loan is paid off (None = not within MAX_MONTHS) and balances:
    total debt left at the start and after each month.
    """
    state = [{**loan, "left": float(loan["balance"]), "done": None} for loan in loans]
    budget = sum(float(loan["payment"]) for loan in loans) + extra
    interest_total, month = 0.0, 0
    balances = [round(sum(s["left"] for s in state), 2)]
    while any(s["left"] > 0.005 for s in state) and month < MAX_MONTHS:
        month += 1
        for s in state:
            if s["left"] > 0.005:
                i = s["left"] * s["rate"] / 100 / 12
                interest_total += i
                s["left"] += i
        money = budget
        # Minimum payments first, then everything left to the highest rate.
        for s in state:
            if s["left"] > 0.005:
                pay = min(float(s["payment"]), s["left"], money)
                s["left"] -= pay
                money -= pay
        for s in sorted(state, key=lambda s: -s["rate"]):
            if money <= 0:
                break
            if s["left"] > 0.005:
                pay = min(s["left"], money)
                s["left"] -= pay
                money -= pay
        for s in state:
            if s["left"] <= 0.005 and s["done"] is None:
                s["done"] = month
        balances.append(round(max(sum(s["left"] for s in state), 0.0), 2))
    finished = all(s["left"] <= 0.005 for s in state)
    return {
        "months": month if finished else None,
        "interest": round(interest_total, 2) if finished else None,
        "paid_off": {s["name"]: s["done"] for s in state},
        "balances": balances,
    }


def loan_payments(df: pd.DataFrame, months: int = 12) -> pd.Series:
    """Average monthly payment per merchant in the 'Loans & credit' category over the last
    `months` months of data (positive kr), largest first."""
    rows = df[(df["category"] == "Loans & credit") & (flow(df) == "spending")]
    if rows.empty:
        return pd.Series(dtype=float)
    start = df["date"].max() - pd.DateOffset(months=months)
    rows = rows[rows["date"] > start]
    return (
        (-rows.groupby("merchant")["amount"].sum() / months).sort_values(ascending=False).round(2)
    )
