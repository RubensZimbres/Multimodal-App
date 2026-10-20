"""Financial statement analysis: extract figures, compute ratios in Python, then comment."""

from app.analyses.common import AnalysisStream, Event, MediaRef, data, delta, status, text_config
from app.config import Settings
from app.finance.ratios import RatioReport, compute_ratios
from app.finance.statement import FinancialStatement
from app.llm import LLM

EXTRACT_PROMPT = """Extract the requested figures from this financial statement.
Use the most recent quarterly period as current_income and the same quarter of the prior
year as prior_income. Use the two balance sheet columns as current_balance and
prior_balance, keeping their printed dates. Copy numbers exactly as printed in the
statement's unit (negative numbers in parentheses become negative). Leave a field null
if the statement does not show it."""

COMMENTARY_PROMPT = """Below are figures extracted from {company}'s financial statement and
ratios computed from them (amounts in {unit} {currency}).

Figures:
{statement}

Ratios (current, prior, change; `improved` says whether the change is favourable):
{ratios}

Write the analysis:
- One short paragraph per ratio: what the value means and whether the trend is good or bad.
- Quote the numbers exactly as given; do not recalculate them.
- Mention the caveats in the notes and any failed consistency checks.
- Finish with a 3-bullet overall assessment of financial health."""


def commentary_prompt(statement: FinancialStatement, report: RatioReport) -> str:
    return COMMENTARY_PROMPT.format(
        company=statement.company_name,
        unit=statement.unit,
        currency=statement.currency,
        statement=statement.model_dump_json(indent=2),
        ratios=report.model_dump_json(indent=2),
    )


async def run_statement(llm: LLM, settings: Settings, document: MediaRef) -> AnalysisStream:
    yield status("Reading the statement and extracting figures")
    statement = await llm.generate_json(
        model=settings.model_default,
        contents=[document.to_part(), EXTRACT_PROMPT],
        schema=FinancialStatement,
    )
    yield data("statement", statement.model_dump())

    report = compute_ratios(statement)
    yield data("ratios", report.model_dump())

    yield status("Writing the analysis")
    async for chunk in llm.stream_text(
        model=settings.model_default,
        contents=[commentary_prompt(statement, report)],
        config=text_config(),
    ):
        yield delta(chunk)
    yield Event("done", {})
