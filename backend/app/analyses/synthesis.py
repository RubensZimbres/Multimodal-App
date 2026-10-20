"""Strategic synthesis across the individual analyses."""

import logging

from pydantic import BaseModel, Field

from app.analyses.common import AnalysisStream, Event, delta, status, text_config
from app.config import Settings
from app.llm import LLM, LLMError

log = logging.getLogger(__name__)

SECTION_TITLES = {
    "market": "Market data, price evolution and news sentiment",
    "statement": "Financial statement analysis",
    "pricing": "Pricing analysis",
    "earnings_call": "Earnings call (management statements)",
    "marketing": "Marketing campaign",
}


class SynthesisInput(BaseModel):
    company: str = Field(min_length=1, max_length=120)
    sections: dict[str, str] = Field(description="Prior analysis outputs keyed by section")


def build_prompt(inp: SynthesisInput) -> str:
    provided = {k: v for k, v in inp.sections.items() if k in SECTION_TITLES and v.strip()}
    if not provided:
        raise ValueError("Run at least one analysis before the synthesis")
    blocks = "\n\n".join(
        f"<section name=\"{k}\" title=\"{SECTION_TITLES[k]}\">\n{v}\n</section>"
        for k, v in provided.items()
    )
    missing = [SECTION_TITLES[k] for k in SECTION_TITLES if k not in provided]
    missing_note = (
        f"\nThese analyses were not run, so do not speculate about them: {', '.join(missing)}."
        if missing
        else ""
    )
    return f"""Prior analyses of {inp.company}:

{blocks}
{missing_note}

Write a strategic report:
1. Executive summary (5 bullets).
2. Inconsistencies or contradictions between the financial statement, management's
   statements and the news. Cite the section each point comes from, e.g. [statement].
3. How the marketing and pricing strategy could be improved given the financials and
   what management said.
4. Key risks and what to watch next quarter."""


async def run_synthesis(llm: LLM, settings: Settings, inp: SynthesisInput) -> AnalysisStream:
    prompt = build_prompt(inp)
    models = list(dict.fromkeys([settings.model_synthesis, settings.model_synthesis_fallback]))
    for i, model in enumerate(models):
        yield status(f"Writing the strategic report with {model}")
        started = False
        try:
            async for chunk in llm.stream_text(
                model=model, contents=[prompt], config=text_config(0.3)
            ):
                started = True
                yield delta(chunk)
        except LLMError:
            # Fall back only if nothing reached the client yet; otherwise text would mix.
            if started or i == len(models) - 1:
                raise
            log.warning("Synthesis model %s failed, falling back", model, exc_info=True)
            continue
        yield Event("done", {"model": model})
        return
