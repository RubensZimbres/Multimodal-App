import logging
from collections.abc import AsyncIterator, Sequence
from typing import Any, Protocol, TypeVar, cast

from google import genai
from google.auth import exceptions as auth_errors
from google.genai import errors, types
from pydantic import BaseModel

from app.config import Settings

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

Contents = Sequence[types.Content | types.Part | str]


class LLMError(RuntimeError):
    pass


class LLM(Protocol):
    def stream_text(
        self,
        *,
        model: str,
        contents: Contents,
        config: types.GenerateContentConfig | None = None,
    ) -> AsyncIterator[str]: ...

    async def generate(
        self,
        *,
        model: str,
        contents: list[types.Content],
        config: types.GenerateContentConfig | None = None,
    ) -> types.GenerateContentResponse: ...

    async def generate_json(
        self,
        *,
        model: str,
        contents: Contents,
        schema: type[T],
        system: str | None = None,
    ) -> T: ...


def _wrap(exc: errors.APIError | auth_errors.GoogleAuthError) -> LLMError:
    if isinstance(exc, auth_errors.GoogleAuthError):
        return LLMError("The server has no valid Google Cloud credentials for Gemini")
    return LLMError(f"Gemini request failed ({exc.code}): {exc.message or exc.status}")


class GeminiLLM:
    def __init__(self, client: genai.Client):
        self._client = client

    @classmethod
    def from_settings(cls, settings: Settings) -> "GeminiLLM":
        client = genai.Client(
            enterprise=True,
            project=settings.gcp_project or None,
            location=settings.gcp_location,
        )
        return cls(client)

    async def stream_text(
        self,
        *,
        model: str,
        contents: Contents,
        config: types.GenerateContentConfig | None = None,
    ) -> AsyncIterator[str]:
        try:
            stream = await self._client.aio.models.generate_content_stream(
                model=model, contents=cast(Any, list(contents)), config=config
            )
            async for chunk in stream:
                if chunk.text:
                    yield chunk.text
        except (errors.APIError, auth_errors.GoogleAuthError) as exc:
            log.exception("stream_text failed")
            raise _wrap(exc) from exc

    async def generate(
        self,
        *,
        model: str,
        contents: list[types.Content],
        config: types.GenerateContentConfig | None = None,
    ) -> types.GenerateContentResponse:
        try:
            return await self._client.aio.models.generate_content(
                model=model, contents=contents, config=config
            )
        except (errors.APIError, auth_errors.GoogleAuthError) as exc:
            log.exception("generate failed")
            raise _wrap(exc) from exc

    async def generate_json(
        self,
        *,
        model: str,
        contents: Contents,
        schema: type[T],
        system: str | None = None,
    ) -> T:
        config = types.GenerateContentConfig(
            temperature=0,
            system_instruction=system,
            response_mime_type="application/json",
            response_schema=schema,
        )
        try:
            response = await self._client.aio.models.generate_content(
                model=model, contents=cast(Any, list(contents)), config=config
            )
        except (errors.APIError, auth_errors.GoogleAuthError) as exc:
            log.exception("generate_json failed")
            raise _wrap(exc) from exc
        if not response.text:
            raise LLMError("Gemini returned an empty structured response")
        return schema.model_validate_json(response.text)
