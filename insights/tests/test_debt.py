import math

import pandas as pd
import pytest

from insights.debt import loan_payments, months_closed_form, payoff, plan, years_table


def test_years_table_derives_rates_and_changes():
    rows = [
        {"year": 2024, "business_profit": 500000, "wages": None, "benefits": None,
         "total_income": 500000, "interest_expense": 50000, "tax_assessed": 125000,
         "debt": 1000000, "net_wealth": 900000, "bank_deposits": 400000},
        {"year": 2025, "business_profit": 300000, "wages": None, "benefits": 100000,
         "total_income": 400000, "interest_expense": 110000, "tax_assessed": 40000,
         "debt": 1200000, "net_wealth": 500000, "bank_deposits": 150000},
    ]  # fmt: skip
    t = years_table(rows)
    assert t.loc[2024, "effective_rate"] == 5.0  # no start-of-year debt: end debt
    assert t.loc[2025, "effective_rate"] == 10.0  # 110 000 / average(1.0 m, 1.2 m)
    assert t.loc[2025, "interest_share"] == 27.5
    assert t.loc[2025, "tax_rate"] == 10.0
    assert t.loc[2025, "debt_change"] == 200000 and t.loc[2025, "deposits_change"] == -250000
    assert years_table([]).empty


def test_payoff_matches_the_annuity_formula():
    result = payoff(100000, 6.0, 2000)
    assert result["months"] == math.ceil(months_closed_form(100000, 6.0, 2000))
    assert 0 < result["interest"] < 2000 * result["months"] - 100000 + 1
    assert payoff(100000, 12.0, 1000) == {"months": None, "interest": None}  # 1 000 = interest
    assert payoff(0, 5, 100) == {"months": 0, "interest": 0.0}


def test_plan_extra_goes_to_highest_rate_and_saves_interest():
    loans = [
        {"name": "cheap", "balance": 50000, "rate": 3.0, "payment": 1000},
        {"name": "dear", "balance": 50000, "rate": 15.0, "payment": 1000},
    ]
    base, faster = plan(loans), plan(loans, extra=2000)
    assert faster["months"] < base["months"]
    assert faster["interest"] < base["interest"]
    assert faster["paid_off"]["dear"] < faster["paid_off"]["cheap"]
    assert plan([{"name": "x", "balance": 10000, "rate": 0, "payment": 1000}])["months"] == 10


def test_loan_payments_average_per_month():
    df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-01", "2026-02-01", "2026-02-15"]),
            "amount": [-1200.0, -1200.0, -600.0],
            "merchant": ["bank", "bank", "card"],
            "category": ["Loans & credit"] * 3,
            "kind": ["fixed"] * 3,
        }
    )
    assert loan_payments(df, months=2).to_dict() == pytest.approx({"bank": 1200, "card": 300})
