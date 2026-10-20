"""Schema Gemini fills in when reading a financial statement.

Values are in the statement's reporting unit (usually millions). Anything the
statement does not show is left null rather than guessed.
"""

from pydantic import BaseModel, Field


class IncomeStatement(BaseModel):
    period_label: str = Field(
        description="Period as printed, e.g. 'Three Months Ended March 30, 2024'"
    )
    total_net_sales: float | None = None
    cost_of_sales: float | None = None
    gross_margin: float | None = Field(default=None, description="Gross profit, not a percentage")
    operating_income: float | None = None
    net_income: float | None = None
    diluted_eps: float | None = None


class BalanceSheet(BaseModel):
    date_label: str = Field(description="Balance sheet date as printed, e.g. 'March 30, 2024'")
    total_current_assets: float | None = None
    total_assets: float | None = None
    total_current_liabilities: float | None = None
    total_liabilities: float | None = None
    total_shareholders_equity: float | None = None
    short_term_debt: float | None = Field(
        default=None,
        description="Debt due within a year: commercial paper plus current term debt",
    )
    long_term_debt: float | None = Field(default=None, description="Non-current term debt")


class FinancialStatement(BaseModel):
    company_name: str
    currency: str = Field(default="USD")
    unit: str = Field(default="millions", description="Reporting unit, e.g. 'millions'")
    current_income: IncomeStatement = Field(
        description="Most recent quarterly (or shortest) period in the statement"
    )
    prior_income: IncomeStatement | None = Field(
        default=None, description="Comparable prior-year period for current_income"
    )
    current_balance: BalanceSheet
    prior_balance: BalanceSheet | None = Field(
        default=None, description="Comparison balance sheet column, whatever date it is"
    )
