"""Market analysis: Gemini function calling over Alpha Vantage."""

import json
from collections.abc import Awaitable, Callable
from typing import Any

from google.genai import types

from app.analyses.common import (
    SYSTEM_PROMPT,
    AnalysisStream,
    Event,
    data,
    delta,
    status,
)
from app.config import Settings
from app.llm import LLM, LLMError
from app.tools.alpha_vantage import NEWS_TOPICS, AlphaVantageClient, MarketDataError

_TICKER_PARAM = {
    "type": "object",
    "properties": {"ticker": {"type": "string", "description": "Stock ticker symbol, e.g. AAPL"}},
    "required": ["ticker"],
}

FUNCTIONS = [
    types.FunctionDeclaration(
        name="get_stock_quote",
        description="Latest price, change and volume for a stock.",
        parameters_json_schema=_TICKER_PARAM,
    ),
    types.FunctionDeclaration(
        name="get_company_overview",
        description="Company profile and fundamentals: sector, market cap, P/E, margins, "
        "analyst target price, 52-week range.",
        parameters_json_schema=_TICKER_PARAM,
    ),
    types.FunctionDeclaration(
        name="get_price_history",
        description="Weekly closing prices, oldest first.",
        parameters_json_schema={
            "type": "object",
            "properties": {
                "ticker": {"type": "string"},
                "weeks": {"type": "integer", "description": "Number of weeks, default 26"},
            },
            "required": ["ticker"],
        },
    ),
    types.FunctionDeclaration(
        name="get_company_news",
        description="Recent news articles about one or more companies, with sentiment.",
        parameters_json_schema={
            "type": "object",
            "properties": {
                "tickers": {"type": "string", "description": "Comma-separated tickers"}
            },
            "required": ["tickers"],
        },
    ),
    types.FunctionDeclaration(
        name="get_topic_news",
        description="Recent market news and sentiment for a topic.",
        parameters_json_schema={
            "type": "object",
            "properties": {"topic": {"type": "string", "enum": sorted(NEWS_TOPICS)}},
            "required": ["topic"],
        },
    ),
]

DEFAULT_QUESTION = """Prepare a market briefing on {ticker}:
- Company overview and key fundamentals (including P/E).
- Share price evolution over the last 6 months, with the main moves.
- The most relevant positive and negative news.
- Overall news sentiment and how it has shifted.
- Key risks and challenges the company faces."""


def _handlers(av: AlphaVantageClient) -> dict[str, Callable[[dict[str, Any]], Awaitable[Any]]]:
    async def history(a: dict[str, Any]) -> Any:
        points = await av.weekly_prices(a["ticker"], int(a.get("weeks") or 26))
        return [p.model_dump() for p in points]

    return {
        "get_stock_quote": lambda a: av.quote(a["ticker"]),
        "get_company_overview": lambda a: av.overview(a["ticker"]),
        "get_price_history": history,
        "get_company_news": lambda a: av.news(tickers=a["tickers"]),
        "get_topic_news": lambda a: av.news(topic=a["topic"]),
    }


async def _call_tool(
    handlers: dict[str, Callable[[dict[str, Any]], Awaitable[Any]]],
    call: types.FunctionCall,
    limit: int,
) -> dict[str, Any]:
    handler = handlers.get(call.name or "")
    if handler is None:
        return {"error": f"Unknown function {call.name}"}
    try:
        result = await handler(dict(call.args or {}))
    except (MarketDataError, KeyError, ValueError) as exc:
        return {"error": str(exc)}
    return {"content": json.dumps(result)[:limit]}


async def run_market(
    llm: LLM,
    av: AlphaVantageClient,
    settings: Settings,
    ticker: str,
    question: str | None = None,
) -> AnalysisStream:
    yield status(f"Fetching price history for {ticker}")
    try:
        prices = await av.weekly_prices(ticker)
        yield data("prices", [p.model_dump() for p in prices])
    except MarketDataError as exc:
        yield status(f"Price chart unavailable: {exc}")

    handlers = _handlers(av)
    config = types.GenerateContentConfig(
        temperature=0,
        system_instruction=SYSTEM_PROMPT,
        tools=[types.Tool(function_declarations=FUNCTIONS)],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    prompt = question or DEFAULT_QUESTION.format(ticker=ticker)
    contents = [types.Content(role="user", parts=[types.Part.from_text(text=prompt)])]

    for _ in range(settings.max_tool_rounds):
        response = await llm.generate(
            model=settings.model_default, contents=contents, config=config
        )
        calls = response.function_calls or []
        if not calls:
            text = response.text or ""
            if not text:
                raise LLMError("Gemini returned an empty answer")
            yield delta(text)
            yield Event("done", {})
            return

        # Keep the model turn verbatim: Gemini 3 needs its thought signatures back.
        if response.candidates and response.candidates[0].content:
            contents.append(response.candidates[0].content)
        parts = []
        for call in calls:
            yield Event("tool_call", {"name": call.name, "args": dict(call.args or {})})
            result = await _call_tool(handlers, call, settings.tool_response_char_limit)
            parts.append(
                types.Part(
                    function_response=types.FunctionResponse(
                        id=call.id, name=call.name, response=result
                    )
                )
            )
        contents.append(types.Content(role="user", parts=parts))

    raise LLMError(f"Stopped after {settings.max_tool_rounds} tool rounds without an answer")
