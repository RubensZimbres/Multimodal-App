from enum import StrEnum

from pydantic import BaseModel, computed_field

from app.finance.statement import BalanceSheet, FinancialStatement, IncomeStatement


class Better(StrEnum):
    HIGHER = "higher"
    LOWER = "lower"


class Ratio(BaseModel):
    key: str
    name: str
    unit: str
    current: float | None
    prior: float | None
    change: float | None
    better_when: Better
    basis: str

    @computed_field  # type: ignore[prop-decorator]
    @property
    def improved(self) -> bool | None:
        if self.change is None or self.change == 0:
            return None
        return (self.change > 0) == (self.better_when is Better.HIGHER)


class RatioReport(BaseModel):
    ratios: list[Ratio]
    checks: list[str]
    notes: list[str]


def _div(a: float | None, b: float | None) -> float | None:
    if a is None or b is None or b == 0:
        return None
    return a / b


def _pct(a: float | None, b: float | None) -> float | None:
    value = _div(a, b)
    return None if value is None else value * 100


def _add(*values: float | None) -> float | None:
    present = [v for v in values if v is not None]
    return sum(present) if present else None


def _change(current: float | None, prior: float | None) -> float | None:
    if current is None or prior is None:
        return None
    return current - prior


def _ratio(
    key: str,
    name: str,
    unit: str,
    current: float | None,
    prior: float | None,
    better: Better,
    basis: str,
) -> Ratio:
    def r(v: float | None) -> float | None:
        return None if v is None else round(v, 4)

    return Ratio(
        key=key,
        name=name,
        unit=unit,
        current=r(current),
        prior=r(prior),
        change=r(_change(current, prior)),
        better_when=better,
        basis=basis,
    )


def _total_debt(b: BalanceSheet | None) -> float | None:
    return None if b is None else _add(b.short_term_debt, b.long_term_debt)


def _income_ratios(cur: IncomeStatement, pri: IncomeStatement | None) -> list[Ratio]:
    basis = f"{cur.period_label} vs {pri.period_label}" if pri else cur.period_label
    p = pri or IncomeStatement(period_label="")
    sales_growth = _pct(_change(cur.total_net_sales, p.total_net_sales), p.total_net_sales)
    return [
        _ratio(
            "gross_margin", "Gross margin", "%",
            _pct(cur.gross_margin, cur.total_net_sales),
            _pct(p.gross_margin, p.total_net_sales),
            Better.HIGHER, basis,
        ),
        _ratio(
            "operating_margin", "Operating margin", "%",
            _pct(cur.operating_income, cur.total_net_sales),
            _pct(p.operating_income, p.total_net_sales),
            Better.HIGHER, basis,
        ),
        _ratio(
            "net_margin", "Net margin", "%",
            _pct(cur.net_income, cur.total_net_sales),
            _pct(p.net_income, p.total_net_sales),
            Better.HIGHER, basis,
        ),
        _ratio("sales_growth", "Sales growth", "%", sales_growth, None, Better.HIGHER, basis),
    ]


def _balance_ratios(cur: BalanceSheet, pri: BalanceSheet | None, unit: str) -> list[Ratio]:
    basis = f"{cur.date_label} vs {pri.date_label}" if pri else cur.date_label
    p = pri or BalanceSheet(date_label="")
    return [
        _ratio(
            "current_ratio", "Liquidity (current ratio)", "x",
            _div(cur.total_current_assets, cur.total_current_liabilities),
            _div(p.total_current_assets, p.total_current_liabilities),
            Better.HIGHER, basis,
        ),
        _ratio(
            "financial_leverage", "Financial leverage (assets / equity)", "x",
            _div(cur.total_assets, cur.total_shareholders_equity),
            _div(p.total_assets, p.total_shareholders_equity),
            Better.LOWER, basis,
        ),
        _ratio(
            "debt_to_equity", "Debt to equity", "x",
            _div(_total_debt(cur), cur.total_shareholders_equity),
            _div(_total_debt(pri), p.total_shareholders_equity),
            Better.LOWER, basis,
        ),
        _ratio(
            "total_debt", "Total debt", unit,
            _total_debt(cur), _total_debt(pri), Better.LOWER, basis,
        ),
        _ratio(
            "long_term_debt", "Long-term debt", unit,
            cur.long_term_debt, p.long_term_debt, Better.LOWER, basis,
        ),
    ]


def _return_ratios(s: FinancialStatement) -> list[Ratio]:
    cur_i, cur_b = s.current_income, s.current_balance
    basis = f"{cur_i.period_label} net income / {cur_b.date_label} balance (not annualized)"
    return [
        _ratio(
            "roa", "Return on assets (period)", "%",
            _pct(cur_i.net_income, cur_b.total_assets), None, Better.HIGHER, basis,
        ),
        _ratio(
            "roe", "Return on equity (period)", "%",
            _pct(cur_i.net_income, cur_b.total_shareholders_equity), None, Better.HIGHER, basis,
        ),
    ]


def _consistency_checks(s: FinancialStatement) -> list[str]:
    issues: list[str] = []
    for b in filter(None, [s.current_balance, s.prior_balance]):
        if None not in (b.total_assets, b.total_liabilities, b.total_shareholders_equity):
            assert b.total_assets is not None
            gap = b.total_assets - (b.total_liabilities or 0) - (b.total_shareholders_equity or 0)
            if abs(gap) > max(1.0, abs(b.total_assets) * 0.001):
                issues.append(
                    f"{b.date_label}: assets differ from liabilities + equity by {gap:,.0f}"
                )
    for i in filter(None, [s.current_income, s.prior_income]):
        if None not in (i.total_net_sales, i.cost_of_sales, i.gross_margin):
            assert i.total_net_sales is not None and i.cost_of_sales is not None
            gap = i.total_net_sales - i.cost_of_sales - (i.gross_margin or 0)
            if abs(gap) > max(1.0, abs(i.total_net_sales) * 0.001):
                issues.append(
                    f"{i.period_label}: sales - cost of sales != gross margin ({gap:,.0f})"
                )
    return issues


def compute_ratios(statement: FinancialStatement) -> RatioReport:
    s = statement
    ratios = [
        *_income_ratios(s.current_income, s.prior_income),
        *_balance_ratios(s.current_balance, s.prior_balance, s.unit),
        *_return_ratios(s),
    ]
    notes: list[str] = []
    if (
        s.prior_balance
        and s.prior_income
        and s.prior_balance.date_label not in s.prior_income.period_label
    ):
        notes.append(
            f"Balance sheet is compared with {s.prior_balance.date_label}, while the income "
            f"statement is compared with {s.prior_income.period_label}. Balance sheet ratios "
            "are therefore not strictly year-over-year."
        )
    notes.append(
        "Price/earnings needs a market price; see the market analysis for the P/E ratio."
    )
    return RatioReport(ratios=ratios, checks=_consistency_checks(s), notes=notes)
