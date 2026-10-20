import json
from collections.abc import AsyncIterator, Callable, Iterator
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from google.genai import types
from pydantic import BaseModel

from app.api.deps import get_market_client
from app.config import Settings
from app.finance.statement import BalanceSheet, FinancialStatement, IncomeStatement
from app.llm import LLMError
from app.main import create_app
from app.tools.alpha_vantage import AlphaVantageClient

AV_URL = "https://av.test/query"


class FakeLLM:
    """Scripted stand-in for GeminiLLM that records every call."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.chunks: list[str] = ["Hello ", "world"]
        self.failing_models: set[str] = set()
        self.json_result: BaseModel | None = None
        self.responses: list[types.GenerateContentResponse] = []

    async def stream_text(
        self, *, model: str, contents: Any, config: Any = None
    ) -> AsyncIterator[str]:
        self.calls.append({"method": "stream_text", "model": model, "contents": list(contents)})
        if model in self.failing_models:
            raise LLMError(f"Gemini request failed (404): model {model} not found")
        for chunk in self.chunks:
            yield chunk

    async def generate(
        self, *, model: str, contents: list[types.Content], config: Any = None
    ) -> types.GenerateContentResponse:
        # Snapshot: the caller keeps mutating the same list between rounds.
        self.calls.append({"method": "generate", "model": model, "contents": list(contents)})
        if not self.responses:
            raise AssertionError("FakeLLM ran out of scripted responses")
        return self.responses.pop(0)

    async def generate_json(
        self, *, model: str, contents: Any, schema: type[BaseModel], system: Any = None
    ) -> BaseModel:
        self.calls.append({"method": "generate_json", "model": model, "contents": list(contents)})
        assert self.json_result is not None, "set FakeLLM.json_result first"
        assert isinstance(self.json_result, schema)
        return self.json_result


def function_call_response(*calls: tuple[str, dict[str, Any]]) -> types.GenerateContentResponse:
    parts = [
        types.Part(function_call=types.FunctionCall(id=f"call-{i}", name=name, args=args))
        for i, (name, args) in enumerate(calls)
    ]
    return types.GenerateContentResponse(
        candidates=[types.Candidate(content=types.Content(role="model", parts=parts))]
    )


def text_response(text: str) -> types.GenerateContentResponse:
    return types.GenerateContentResponse(
        candidates=[
            types.Candidate(
                content=types.Content(role="model", parts=[types.Part.from_text(text=text)])
            )
        ]
    )


def apple_q2_fy24() -> FinancialStatement:
    """Figures from Apple's FY24 Q2 condensed consolidated statements (USD millions)."""
    return FinancialStatement(
        company_name="Apple Inc.",
        current_income=IncomeStatement(
            period_label="Three Months Ended March 30, 2024",
            total_net_sales=90_753, cost_of_sales=48_482, gross_margin=42_271,
            operating_income=27_900, net_income=23_636, diluted_eps=1.53,
        ),
        prior_income=IncomeStatement(
            period_label="Three Months Ended April 1, 2023",
            total_net_sales=94_836, cost_of_sales=52_860, gross_margin=41_976,
            operating_income=28_318, net_income=24_160, diluted_eps=1.52,
        ),
        current_balance=BalanceSheet(
            date_label="March 30, 2024",
            total_current_assets=128_416, total_assets=337_411,
            total_current_liabilities=123_822, total_liabilities=263_217,
            total_shareholders_equity=74_194,
            short_term_debt=1_997 + 10_762, long_term_debt=91_831,
        ),
        prior_balance=BalanceSheet(
            date_label="September 30, 2023",
            total_current_assets=143_566, total_assets=352_583,
            total_current_liabilities=145_308, total_liabilities=290_437,
            total_shareholders_equity=62_146,
            short_term_debt=5_985 + 9_822, long_term_debt=95_281,
        ),
    )


AV_FIXTURES: dict[str, dict[str, Any]] = {
    "GLOBAL_QUOTE": {"Global Quote": {"01. symbol": "AAPL", "05. price": "170.0000"}},
    "OVERVIEW": {"Symbol": "AAPL", "Name": "Apple Inc", "PERatio": "28.1", "EBITDA": "None"},
    "TIME_SERIES_WEEKLY": {
        "Weekly Time Series": {
            f"2024-{m:02d}-01": {"4. close": str(150 + m), "5. volume": "1000"}
            for m in range(1, 13)
        }
    },
    "NEWS_SENTIMENT": {
        "feed": [
            {
                "title": "Apple beats estimates",
                "source": "Wire",
                "time_published": "20240503T000000",
                "url": "https://example.com/a",
                "summary": "x" * 1000,
                "overall_sentiment_label": "Bullish",
                "overall_sentiment_score": 0.4,
                "ticker_sentiment": [
                    {"ticker": "AAPL", "ticker_sentiment_label": "Bullish", "relevance_score": "0.9"},
                    {"ticker": "MSFT", "ticker_sentiment_label": "Neutral", "relevance_score": "0.1"},
                ],
            }
        ]
    },
}


def av_transport(
    overrides: dict[str, dict[str, Any]] | None = None,
    seen: list[httpx.Request] | None = None,
) -> httpx.MockTransport:
    fixtures = {**AV_FIXTURES, **(overrides or {})}

    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        fn = request.url.params["function"]
        return httpx.Response(200, json=fixtures[fn])

    return httpx.MockTransport(handler)


@pytest.fixture
def settings() -> Settings:
    return Settings(
        GOOGLE_CLOUD_PROJECT="test-project",
        alpha_vantage_api_key="test-key",
        alpha_vantage_base_url=AV_URL,
        upload_bucket="uploads-bucket",
        auth_required=False,
    )


@pytest.fixture
def fake_llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture
def make_av() -> Callable[..., AlphaVantageClient]:
    def make(
        overrides: dict[str, dict[str, Any]] | None = None,
        seen: list[httpx.Request] | None = None,
        api_key: str = "test-key",
    ) -> AlphaVantageClient:
        http = httpx.AsyncClient(transport=av_transport(overrides, seen))
        return AlphaVantageClient(api_key, AV_URL, http)

    return make


@pytest.fixture
def client(
    settings: Settings, fake_llm: FakeLLM, make_av: Callable[..., AlphaVantageClient]
) -> Iterator[TestClient]:
    app = create_app(settings, llm=fake_llm)
    app.dependency_overrides[get_market_client] = lambda: make_av()
    with TestClient(app) as c:
        yield c


def parse_sse(body: str) -> list[tuple[str, dict[str, Any]]]:
    events = []
    for block in body.replace("\r\n", "\n").split("\n\n"):
        name, payload = None, None
        for line in block.splitlines():
            if line.startswith("event:"):
                name = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                payload = line.split(":", 1)[1].strip()
        if name and payload is not None:
            events.append((name, json.loads(payload)))
    return events
