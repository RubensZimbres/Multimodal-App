"""Image, audio and video analysis with task presets."""

from enum import StrEnum

from app.analyses.common import AnalysisStream, Event, MediaRef, delta, status, text_config
from app.config import Settings
from app.llm import LLM


class MediaTask(StrEnum):
    PRICING = "pricing"
    EARNINGS_CALL = "earnings_call"
    MARKETING = "marketing"
    CUSTOM = "custom"


PRESETS: dict[MediaTask, str] = {
    MediaTask.PRICING: """This image shows product prices. For {company}:
- For each product, which country or market has the highest and lowest price?
- What does the spread suggest about the pricing strategy (premium, regional, FX-driven)?
Present the per-product findings as a Markdown table.""",
    MediaTask.EARNINGS_CALL: """This is an earnings call or executive statement from {company}.
- Key takeaways from each speaker (identify CEO, CFO or others where possible).
- Guidance, targets or numbers mentioned, with timestamps.
- The tone of each speaker: positive, neutral or negative, and why.
- Topics that were avoided or answered vaguely.""",
    MediaTask.MARKETING: """This is a marketing video from {company}.
- What is shown, scene by scene (brief, with timestamps).
- Which product features are emphasized and what selling strategy is used.
- The emotional appeal and target audience.
- Strengths and weaknesses of the campaign.""",
}


def build_prompt(task: MediaTask, company: str, question: str | None) -> str:
    if task is MediaTask.CUSTOM:
        if not question:
            raise ValueError("A question is required for a custom media analysis")
        return question
    prompt = PRESETS[task].format(company=company)
    return f"{prompt}\n\nAlso address: {question}" if question else prompt


async def run_media(
    llm: LLM,
    settings: Settings,
    media: list[MediaRef],
    task: MediaTask,
    company: str,
    question: str | None = None,
) -> AnalysisStream:
    prompt = build_prompt(task, company, question)
    yield status(f"Analyzing {len(media)} file(s)")
    async for chunk in llm.stream_text(
        model=settings.model_default,
        contents=[*(m.to_part() for m in media), prompt],
        config=text_config(),
    ):
        yield delta(chunk)
    yield Event("done", {})
