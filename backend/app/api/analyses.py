import json
import logging
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, StringConstraints
from sse_starlette import EventSourceResponse, ServerSentEvent

from app.analyses.common import AnalysisStream, MediaNotAllowed, MediaRef, check_media
from app.analyses.market import run_market
from app.analyses.media import MediaTask, run_media
from app.analyses.statement import run_statement
from app.analyses.synthesis import SynthesisInput, run_synthesis
from app.api.deps import LLMDep, MarketDep, SettingsDep, UserDep
from app.config import Settings
from app.llm import LLMError
from app.tools.alpha_vantage import MarketDataError, normalize_ticker

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/analyses", tags=["analyses"])

Question = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]


class MarketRequest(BaseModel):
    ticker: str
    question: Question | None = None


class StatementRequest(BaseModel):
    document: MediaRef


class MediaRequest(BaseModel):
    media: list[MediaRef] = Field(min_length=1, max_length=5)
    task: MediaTask
    company: str = Field(min_length=1, max_length=120)
    question: Question | None = None


def _authorize_media(items: list[MediaRef], user: str, settings: Settings) -> None:
    try:
        for m in items:
            check_media(m, user, settings)
    except MediaNotAllowed as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc


async def _sse(stream: AnalysisStream) -> AsyncIterator[ServerSentEvent]:
    """Expected failures become an `error` event; the HTTP status is already 200."""
    try:
        async for event in stream:
            yield ServerSentEvent(event=event.type, data=json.dumps(event.data))
    except (LLMError, MarketDataError, ValueError) as exc:
        yield ServerSentEvent(event="error", data=json.dumps({"message": str(exc)}))
    except Exception:
        log.exception("Analysis failed")
        yield ServerSentEvent(
            event="error", data=json.dumps({"message": "Unexpected server error"})
        )


def _respond(stream: AnalysisStream) -> EventSourceResponse:
    return EventSourceResponse(_sse(stream), ping=15)


@router.post("/market")
async def market(
    body: MarketRequest, llm: LLMDep, av: MarketDep, settings: SettingsDep, user: UserDep
) -> EventSourceResponse:
    try:
        ticker = normalize_ticker(body.ticker)
    except MarketDataError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return _respond(run_market(llm, av, settings, ticker, body.question))


@router.post("/statement")
async def statement(
    body: StatementRequest, llm: LLMDep, settings: SettingsDep, user: UserDep
) -> EventSourceResponse:
    if body.document.mime_type != "application/pdf":
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Statement must be a PDF")
    _authorize_media([body.document], user, settings)
    return _respond(run_statement(llm, settings, body.document))


@router.post("/media")
async def media(
    body: MediaRequest, llm: LLMDep, settings: SettingsDep, user: UserDep
) -> EventSourceResponse:
    _authorize_media(body.media, user, settings)
    return _respond(
        run_media(llm, settings, body.media, body.task, body.company, body.question)
    )


@router.post("/synthesis")
async def synthesis(
    body: SynthesisInput, llm: LLMDep, settings: SettingsDep, user: UserDep
) -> EventSourceResponse:
    return _respond(run_synthesis(llm, settings, body))
