"""The Ask-your-data tools on the synthetic demo data (no model involved)."""

from datetime import date
from io import StringIO

import pytest
from django.core.management import call_command

from ai.tools import TOOLS, Data, ToolError, run

pytestmark = pytest.mark.django_db
END, TODAY = date(2026, 10, 31), date(2026, 11, 1)


@pytest.fixture
def data():
    call_command("make_demo_data", end=END, stdout=StringIO())
    return Data(today=TODAY)


def test_context_tells_the_model_dates_and_names(data):
    ctx = data.context()
    assert ctx["today"] == "2026-11-01" and ctx["last_complete_month"] == "2026-10"
    assert ctx["first_date"] == "2024-11-01" and ctx["last_date"] == "2026-10-31"
    assert "Groceries" in ctx["groups_and_categories"]["Food"]


def test_every_tool_has_a_valid_schema():
    for tool in TOOLS.values():
        schema = tool.schema()
        assert schema["type"] == "object"
        assert set(tool.required) <= set(schema["properties"])
        assert len(tool.description) > 40


def test_monthly_overview_defaults_to_the_last_12_complete_months(data):
    result, spec = run(data, "monthly_overview", {})
    months = [m["month"] for m in result["months"]]
    assert months[0] == "2025-11" and months[-1] == "2026-10" and len(months) == 12
    first = result["months"][0]
    assert first["net"] == first["income"] - first["spending"]
    assert spec["kind"] == "bar" and len(spec["x"]) == 12


def test_spending_for_a_group_and_the_split_without_one(data):
    food, _ = run(data, "spending", {"group": "food", "from": "2026-06", "to": "2026-08"})
    assert food["group"] == "Food" and list(food["per_month"]) == ["2026-06", "2026-07", "2026-08"]
    assert food["total"] == pytest.approx(sum(food["per_month"].values()), abs=2)  # rounding
    everything, spec = run(data, "spending", {"from": "2026-06", "to": "2026-08"})
    assert everything["per_group"]["Food"] == food["total"]
    assert next(iter(everything["per_group"])) == "Housing"  # largest first
    assert spec["horizontal"]


def test_compare_periods_reports_the_change_from_a_to_b(data):
    args = {"a_from": "2025-06", "a_to": "2025-08", "b_from": "2026-06", "b_to": "2026-08"}
    result, _ = run(data, "compare_periods", args)
    housing = result["per_group"]["Housing"]
    assert housing["change"] == pytest.approx(housing["b"] - housing["a"], abs=1)
    assert housing["b"] > housing["a"]  # the rent went up in the second year


def test_recurring_finds_the_price_rises(data):
    result, _ = run(data, "recurring_payments", {})
    rises = {p["name"]: p["price_change_percent"] for p in result["payments"]}
    assert rises["spotify p2c"] > 0 and rises["sats norge"] > 0


def test_unusual_months_finds_the_car_repair(data):
    result, spec = run(data, "unusual_months", {})
    assert spec is None
    assert any(u["group"] == "Transport" and u["month"] == "2026-08" for u in result["unusual"])


def test_debt_payoff_gives_months_dates_and_savings(data):
    result, spec = run(data, "debt_payoff", {"extra_per_month": 3000})
    base, extra = result["current_pace"], result["with_extra"]
    assert extra["months_until_debt_free"] < base["months_until_debt_free"]
    assert extra["months_saved"] == base["months_until_debt_free"] - extra["months_until_debt_free"]
    assert extra["interest_saved"] == pytest.approx(
        base["total_interest"] - extra["total_interest"], abs=1
    )
    assert extra["debt_free_month"] > "2026-11"
    assert len(spec["series"]) == 2


def test_budget_status_and_a_month_without_budget(data):
    result, _ = run(data, "budget_status", {"month": "2026-10"})
    assert {g["status"] for g in result["groups"]} <= {"on track", "at risk", "over"}
    with pytest.raises(ToolError, match="No budget"):
        run(data, "budget_status", {"month": "2025-01"})


def test_find_transactions_sums_one_merchant(data):
    result, _ = run(data, "find_transactions", {"text": "SPOTIFY", "limit": 3})
    assert result["matches"] == 24 and len(result["newest"]) == 3
    assert result["money_out"] == 129 * 12 + 149 * 12
    assert result["newest"][0]["date"] > result["newest"][1]["date"]


@pytest.mark.parametrize(
    "name, args, message",
    [
        ("nope", {}, "Unknown tool"),
        ("spending", {"group": "Fun"}, "Unknown group 'Fun'. Use one of: "),
        ("spending", {"to": "soon"}, "must be a month like"),
        ("monthly_overview", {"from": "2026-05", "to": "2026-01"}, "is after"),
        ("monthly_overview", {"from": "2030-01", "to": "2030-02"}, "No data in"),
        ("compare_periods", {"a_from": "2025-01"}, "Missing argument"),
        ("find_transactions", {"text": "a"}, "at least 2"),
        ("debt_payoff", {"extra_per_month": -5}, "between 0"),
    ],
)
def test_bad_arguments_become_messages_for_the_model(data, name, args, message):
    with pytest.raises(ToolError, match=message):
        run(data, name, args)


def test_no_data_at_all():
    data = Data(today=TODAY)
    assert data.context()["data"] == "no transactions yet"
