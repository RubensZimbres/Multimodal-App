import pytest

from app.finance.ratios import Better, compute_ratios
from app.finance.statement import BalanceSheet, FinancialStatement, IncomeStatement
from tests.conftest import apple_q2_fy24


def by_key(statement: FinancialStatement) -> dict[str, dict[str, object]]:
    return {r.key: r.model_dump() for r in compute_ratios(statement).ratios}


def test_apple_ratios_match_hand_calculation() -> None:
    r = by_key(apple_q2_fy24())

    assert r["current_ratio"]["current"] == pytest.approx(128_416 / 123_822, abs=1e-4)
    assert r["current_ratio"]["prior"] == pytest.approx(143_566 / 145_308, abs=1e-4)
    assert r["financial_leverage"]["current"] == pytest.approx(4.5477, abs=1e-4)
    assert r["financial_leverage"]["prior"] == pytest.approx(5.6735, abs=1e-4)
    assert r["gross_margin"]["current"] == pytest.approx(46.578, abs=1e-3)
    assert r["gross_margin"]["prior"] == pytest.approx(44.262, abs=1e-3)
    assert r["net_margin"]["current"] == pytest.approx(26.044, abs=1e-3)
    assert r["sales_growth"]["current"] == pytest.approx(-4.3054, abs=1e-4)
    assert r["total_debt"]["current"] == 104_590
    assert r["total_debt"]["prior"] == 111_088
    assert r["long_term_debt"]["change"] == 91_831 - 95_281
    assert r["roe"]["current"] == pytest.approx(31.857, abs=1e-3)
    assert r["roa"]["current"] == pytest.approx(7.005, abs=1e-3)
    assert r["roe"]["prior"] is None


def test_improved_respects_direction() -> None:
    r = by_key(apple_q2_fy24())
    assert r["gross_margin"]["improved"] is True
    assert r["financial_leverage"]["improved"] is True
    assert r["total_debt"]["improved"] is True
    assert r["financial_leverage"]["better_when"] == Better.LOWER
    assert r["sales_growth"]["improved"] is None


def test_apple_passes_consistency_checks_and_flags_period_mismatch() -> None:
    report = compute_ratios(apple_q2_fy24())
    assert report.checks == []
    assert any("September 30, 2023" in n and "not strictly" in n for n in report.notes)


def test_inconsistent_balance_sheet_is_reported() -> None:
    s = apple_q2_fy24()
    s.current_balance.total_liabilities = 200_000
    checks = compute_ratios(s).checks
    assert len(checks) == 1 and "March 30, 2024" in checks[0]


def test_missing_values_and_zero_division_yield_none() -> None:
    s = FinancialStatement(
        company_name="Tiny Co",
        current_income=IncomeStatement(period_label="Q1", total_net_sales=0, net_income=5),
        current_balance=BalanceSheet(date_label="Mar 31", total_shareholders_equity=0),
    )
    r = by_key(s)
    assert r["net_margin"]["current"] is None
    assert r["roe"]["current"] is None
    assert r["current_ratio"]["current"] is None
    assert r["total_debt"]["current"] is None
    assert all(v["change"] is None for v in r.values())
