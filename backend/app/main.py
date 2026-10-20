import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import analyses, demo, uploads
from app.config import Settings, get_settings
from app.llm import LLM, GeminiLLM

logging.basicConfig(level=logging.INFO)


def create_app(settings: Settings | None = None, llm: LLM | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.llm = llm or GeminiLLM.from_settings(settings)
        async with httpx.AsyncClient(timeout=httpx.Timeout(20.0)) as http:
            app.state.http = http
            yield

    app = FastAPI(title="Multimodal Analyst API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )
    app.dependency_overrides[get_settings] = lambda: settings
    app.include_router(demo.router)
    app.include_router(analyses.router)
    app.include_router(uploads.router)

    @app.get("/api/health")
    async def health() -> dict[str, str | bool]:
        return {
            "status": "ok",
            "model": settings.model_default,
            "uploads": bool(settings.upload_bucket),
            "auth": settings.auth_required,
        }

    return app


app = create_app()
