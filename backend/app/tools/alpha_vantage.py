"""Async Alpha Vantage client returning compact, model-friendly data.

Alpha Vantage answers rate limits and bad keys with HTTP 200 plus a "Note",
"Information" or "Error Message" field, so those are turned into errors here.
"""

import re
from typing import Any

import httpx
from pydantic import BaseModel

TICKER_RE = re.compile(r"^[A-Z0-9.\-]{1,12}$")

NEWS_TOPICS = frozenset({
    "blockchain", "earnings", "ipo", "mergers_and_acquisitions", "financial_markets",
    "economy_fiscal", "economy_monetary", "economy_macro", "energy_transportation",
    "finance", "life_sciences", "manufacturing", "real_estate", "retail_wholesale",
    "technology",
})


class MarketDataError(RuntimeError):
    pass


class PricePoint(BaseModel):
    date: str
    close: float
    volume: int


def normalize_ticker(ticker: str) -> str:
    t = ticker.strip().upper()
    if not TICKER_RE.match(t):
        raise MarketDataError(f"Invalid ticker symbol: {ticker!r}")
    return t


class AlphaVantageClient:
    def __init__(self, api_key: str, base_url: str, http: httpx.AsyncClient):
        self._key = api_key
        self._base = base_url
        self._http = http

    async def _query(self, **params: str) -> dict[str, Any]:
        if not self._key:
            raise MarketDataError("ALPHA_VANTAGE_API_KEY is not configured")
        try:
            resp = await self._http.get(self._base, params={**params, "apikey": self._key})
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise MarketDataError(f"Alpha Vantage request failed: {exc}") from exc
        for key in ("Error Message", "Note", "Information"):
            if key in data:
                raise MarketDataError(f"Alpha Vantage: {data[key]}")
        return data

    async def quote(self, ticker: str) -> dict[str, str]:
        data = await self._query(function="GLOBAL_QUOTE", symbol=normalize_ticker(ticker))
        raw = data.get("Global Quote") or {}
        if not raw:
            raise MarketDataError(f"No quote found for {ticker}")
        # Keys look like "05. price"; strip the numeric prefix.
        return {k.split(". ", 1)[-1]: v for k, v in raw.items()}

    async def overview(self, ticker: str) -> dict[str, str]:
        data = await self._query(function="OVERVIEW", symbol=normalize_ticker(ticker))
        if not data:
            raise MarketDataError(f"No company overview found for {ticker}")
        return {k: v for k, v in data.items() if v not in ("None", "-", "")}

    async def weekly_prices(self, ticker: str, weeks: int = 26) -> list[PricePoint]:
        """Weekly closes, oldest first. Weekly series are on the free tier."""
        data = await self._query(function="TIME_SERIES_WEEKLY", symbol=normalize_ticker(ticker))
        series = data.get("Weekly Time Series") or {}
        if not series:
            raise MarketDataError(f"No price history found for {ticker}")
        latest = sorted(series.items(), reverse=True)[: max(1, min(weeks, 260))]
        return [
            PricePoint(date=d, close=float(v["4. close"]), volume=int(v["5. volume"]))
            for d, v in reversed(latest)
        ]

    async def news(
        self, *, tickers: str | None = None, topic: str | None = None, limit: int = 20
    ) -> list[dict[str, Any]]:
        params = {"function": "NEWS_SENTIMENT", "sort": "RELEVANCE", "limit": str(limit)}
        if tickers:
            params["tickers"] = ",".join(normalize_ticker(t) for t in tickers.split(","))
        if topic:
            if topic not in NEWS_TOPICS:
                raise MarketDataError(f"Unsupported news topic: {topic}")
            params["topics"] = topic
        data = await self._query(**params)
        items = []
        for item in (data.get("feed") or [])[:limit]:
            entry: dict[str, Any] = {
                "title": item.get("title"),
                "source": item.get("source"),
                "published": item.get("time_published"),
                "url": item.get("url"),
                "summary": (item.get("summary") or "")[:400],
                "overall_sentiment": item.get("overall_sentiment_label"),
                "overall_score": item.get("overall_sentiment_score"),
            }
            if tickers:
                wanted = set(params["tickers"].split(","))
                entry["ticker_sentiment"] = [
                    {k: t.get(k) for k in ("ticker", "ticker_sentiment_label", "relevance_score")}
                    for t in item.get("ticker_sentiment") or []
                    if t.get("ticker") in wanted
                ]
            items.append(entry)
        return items
