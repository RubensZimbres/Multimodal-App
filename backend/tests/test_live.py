import os

import pytest

from app.analyses.common import MediaRef
from app.analyses.statement import EXTRACT_PROMPT
from app.config import Settings
from app.finance.statement import FinancialStatement
from app.llm import GeminiLLM
from tests.conftest import apple_q2_fy24

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not os.getenv("RUN_LIVE_TESTS"), reason="set RUN_LIVE_TESTS=1"),
]

DEMO_PDF = MediaRef(
    uri="gs://bucket-15-storage/FY24_Q2_Consolidated_Financial_Statements.pdf",
    mime_type="application/pdf",
)


async def test_model_answers() -> None:
    settings = Settings()
    llm = GeminiLLM.from_settings(settings)
    chunks = [c async for c in llm.stream_text(model=settings.model_default, contents=["Say OK"])]
    assert "".join(chunks).strip()


async def test_demo_statement_extraction_matches_printed_figures() -> None:
    settings = Settings()
    llm = GeminiLLM.from_settings(settings)
    got = await llm.generate_json(
        model=settings.model_default,
        contents=[DEMO_PDF.to_part(), EXTRACT_PROMPT],
        schema=FinancialStatement,
    )
    expected = apple_q2_fy24()
    assert got.current_income.model_dump(exclude={"period_label"}) == pytest.approx(
        expected.current_income.model_dump(exclude={"period_label"})
    )
    assert got.prior_income is not None and expected.prior_income is not None
    assert got.prior_income.net_income == expected.prior_income.net_income
    assert got.current_balance.total_assets == expected.current_balance.total_assets
    assert got.current_balance.short_term_debt == expected.current_balance.short_term_debt
    assert got.current_balance.long_term_debt == expected.current_balance.long_term_debt
    assert got.prior_balance is not None and "September" in got.prior_balance.date_label
