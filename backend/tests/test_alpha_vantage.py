from collections.abc import Callable

import httpx
import pytest

from app.tools.alpha_vantage import AlphaVantageClient, MarketDataError, normalize_ticker

MakeAV = Callable[..., AlphaVantageClient]


async def test_quote_strips_numeric_prefixes(make_av: MakeAV) -> None:
    quote = await make_av().quote("aapl")
    assert quote == {"symbol": "AAPL", "price": "170.0000"}


async def test_overview_drops_empty_values(make_av: MakeAV) -> None:
    overview = await make_av().overview("AAPL")
    assert overview["PERatio"] == "28.1"
    assert "EBITDA" not in overview


async def test_weekly_prices_are_trimmed_and_oldest_first(make_av: MakeAV) -> None:
    points = await make_av().weekly_prices("AAPL", weeks=3)
    assert [p.date for p in points] == ["2024-10-01", "2024-11-01", "2024-12-01"]
    assert points[-1].close == 162.0


async def test_news_filters_ticker_sentiment_and_truncates(make_av: MakeAV) -> None:
    seen: list[httpx.Request] = []
    items = await make_av(seen=seen).news(tickers="aapl")
    assert seen[0].url.params["tickers"] == "AAPL"
    assert len(items[0]["summary"]) == 400
    assert [t["ticker"] for t in items[0]["ticker_sentiment"]] == ["AAPL"]


async def test_api_key_is_sent(make_av: MakeAV) -> None:
    seen: list[httpx.Request] = []
    await make_av(seen=seen).quote("AAPL")
    assert seen[0].url.params["apikey"] == "test-key"


@pytest.mark.parametrize("field", ["Note", "Information", "Error Message"])
async def test_soft_errors_raise(make_av: MakeAV, field: str) -> None:
    av = make_av({"GLOBAL_QUOTE": {field: "rate limit reached"}})
    with pytest.raises(MarketDataError, match="rate limit"):
        await av.quote("AAPL")


async def test_missing_key_raises_without_calling(make_av: MakeAV) -> None:
    seen: list[httpx.Request] = []
    with pytest.raises(MarketDataError, match="not configured"):
        await make_av(seen=seen, api_key="").quote("AAPL")
    assert seen == []


async def test_unknown_topic_rejected(make_av: MakeAV) -> None:
    with pytest.raises(MarketDataError, match="topic"):
        await make_av().news(topic="gossip")


async def test_http_error_wrapped() -> None:
    http = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(503)))
    with pytest.raises(MarketDataError, match="request failed"):
        await AlphaVantageClient("k", "https://av.test/query", http).quote("AAPL")


@pytest.mark.parametrize("bad", ["", "AAPL&apikey=x", "a" * 13, "AA PL"])
def test_invalid_tickers_rejected(bad: str) -> None:
    with pytest.raises(MarketDataError):
        normalize_ticker(bad)


def test_ticker_normalized() -> None:
    assert normalize_ticker(" brk.b ") == "BRK.B"
