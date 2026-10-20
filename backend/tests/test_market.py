import json
from collections.abc import Callable

import pytest

from app.analyses.common import Event
from app.analyses.market import run_market
from app.config import Settings
from app.llm import LLMError
from app.tools.alpha_vantage import AlphaVantageClient
from tests.conftest import FakeLLM, function_call_response, text_response

MakeAV = Callable[..., AlphaVantageClient]


async def collect(stream: object) -> list[Event]:
    return [e async for e in stream]  # type: ignore[attr-defined]


async def test_parallel_tool_calls_are_all_executed(
    fake_llm: FakeLLM, make_av: MakeAV, settings: Settings
) -> None:
    fake_llm.responses = [
        function_call_response(
            ("get_stock_quote", {"ticker": "AAPL"}),
            ("get_company_news", {"tickers": "AAPL"}),
        ),
        text_response("## Briefing"),
    ]
    events = await collect(run_market(fake_llm, make_av(), settings, "AAPL"))

    tool_calls = [e.data["name"] for e in events if e.type == "tool_call"]
    assert tool_calls == ["get_stock_quote", "get_company_news"]
    assert [e.type for e in events][-2:] == ["delta", "done"]
    assert events[-2].data["text"] == "## Briefing"

    # Second request = prompt, model turn (verbatim), one user turn with both responses.
    history = fake_llm.calls[1]["contents"]
    assert [c.role for c in history] == ["user", "model", "user"]
    responses = [p.function_response for p in history[2].parts]
    assert [(r.id, r.name) for r in responses] == [
        ("call-0", "get_stock_quote"),
        ("call-1", "get_company_news"),
    ]
    assert json.loads(responses[0].response["content"])["price"] == "170.0000"


async def test_chart_data_emitted_before_model_runs(
    fake_llm: FakeLLM, make_av: MakeAV, settings: Settings
) -> None:
    fake_llm.responses = [text_response("ok")]
    events = await collect(run_market(fake_llm, make_av(), settings, "AAPL"))
    prices = next(e for e in events if e.type == "data")
    assert prices.data["kind"] == "prices"
    assert len(prices.data["payload"]) == 12


async def test_tool_errors_are_returned_to_the_model(
    fake_llm: FakeLLM, make_av: MakeAV, settings: Settings
) -> None:
    av = make_av({"OVERVIEW": {"Note": "rate limit"}})
    fake_llm.responses = [
        function_call_response(("get_company_overview", {"ticker": "AAPL"})),
        function_call_response(("does_not_exist", {})),
        text_response("done"),
    ]
    await collect(run_market(fake_llm, av, settings, "AAPL"))
    first = fake_llm.calls[1]["contents"][-1].parts[0].function_response.response
    second = fake_llm.calls[2]["contents"][-1].parts[0].function_response.response
    assert "rate limit" in first["error"]
    assert "Unknown function" in second["error"]


async def test_tool_output_is_truncated(
    fake_llm: FakeLLM, make_av: MakeAV, settings: Settings
) -> None:
    settings.tool_response_char_limit = 50
    fake_llm.responses = [
        function_call_response(("get_price_history", {"ticker": "AAPL", "weeks": 12})),
        text_response("ok"),
    ]
    await collect(run_market(fake_llm, make_av(), settings, "AAPL"))
    content = fake_llm.calls[1]["contents"][-1].parts[0].function_response.response["content"]
    assert len(content) == 50


async def test_price_chart_failure_is_not_fatal(
    fake_llm: FakeLLM, make_av: MakeAV, settings: Settings
) -> None:
    av = make_av({"TIME_SERIES_WEEKLY": {"Note": "rate limit"}})
    fake_llm.responses = [text_response("ok")]
    events = await collect(run_market(fake_llm, av, settings, "AAPL"))
    assert any(e.type == "status" and "unavailable" in e.data["message"] for e in events)
    assert events[-1].type == "done"


async def test_runaway_tool_loop_stops(
    fake_llm: FakeLLM, make_av: MakeAV, settings: Settings
) -> None:
    settings.max_tool_rounds = 2
    fake_llm.responses = [function_call_response(("get_stock_quote", {"ticker": "AAPL"}))] * 2
    with pytest.raises(LLMError, match="2 tool rounds"):
        await collect(run_market(fake_llm, make_av(), settings, "AAPL"))


async def test_custom_question_replaces_default_prompt(
    fake_llm: FakeLLM, make_av: MakeAV, settings: Settings
) -> None:
    fake_llm.responses = [text_response("ok")]
    await collect(run_market(fake_llm, make_av(), settings, "MSFT", "Is MSFT expensive?"))
    assert fake_llm.calls[0]["contents"][0].parts[0].text == "Is MSFT expensive?"
