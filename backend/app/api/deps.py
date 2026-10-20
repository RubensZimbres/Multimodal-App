from typing import Annotated

import firebase_admin
from fastapi import Depends, Header, HTTPException, Request, status
from firebase_admin import auth as fb_auth
from starlette.concurrency import run_in_threadpool

from app.config import Settings, get_settings
from app.llm import LLM
from app.tools.alpha_vantage import AlphaVantageClient

SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_llm(request: Request) -> LLM:
    llm: LLM = request.app.state.llm
    return llm


def get_market_client(request: Request, settings: SettingsDep) -> AlphaVantageClient:
    return AlphaVantageClient(
        settings.alpha_vantage_api_key, settings.alpha_vantage_base_url, request.app.state.http
    )


async def get_user_id(
    settings: SettingsDep, authorization: Annotated[str | None, Header()] = None
) -> str:
    """Verify the Firebase ID token sent by the frontend and return the user's uid."""
    if not settings.auth_required:
        return "dev"
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    if not firebase_admin._apps:
        firebase_admin.initialize_app(options={"projectId": settings.gcp_project or None})
    try:
        claims = await run_in_threadpool(fb_auth.verify_id_token, authorization[7:])
    except (ValueError, fb_auth.InvalidIdTokenError, fb_auth.ExpiredIdTokenError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token") from exc
    uid: str = claims["uid"]
    return uid


LLMDep = Annotated[LLM, Depends(get_llm)]
MarketDep = Annotated[AlphaVantageClient, Depends(get_market_client)]
UserDep = Annotated[str, Depends(get_user_id)]
