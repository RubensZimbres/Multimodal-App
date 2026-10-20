from types import SimpleNamespace
from typing import Any

import pytest
from google.auth.exceptions import DefaultCredentialsError
from google.genai import errors

from app.finance.statement import BalanceSheet
from app.llm import GeminiLLM, LLMError


def llm_raising(exc: Exception) -> GeminiLLM:
    async def fail(**_: Any) -> None:
        raise exc

    models = SimpleNamespace(generate_content=fail, generate_content_stream=fail)
    return GeminiLLM(SimpleNamespace(aio=SimpleNamespace(models=models)))  # type: ignore[arg-type]


async def test_missing_credentials_become_readable_error() -> None:
    llm = llm_raising(DefaultCredentialsError("no ADC"))
    with pytest.raises(LLMError, match="no valid Google Cloud credentials"):
        await llm.generate(model="m", contents=[])
    with pytest.raises(LLMError, match="credentials"):
        [c async for c in llm.stream_text(model="m", contents=["hi"])]


async def test_api_errors_carry_status() -> None:
    llm = llm_raising(errors.ClientError(404, {"error": {"message": "model not found"}}))
    with pytest.raises(LLMError, match=r"\(404\): model not found"):
        await llm.generate_json(model="m", contents=["x"], schema=BalanceSheet)


async def test_structured_output_is_validated() -> None:
    async def ok(**_: Any) -> Any:
        return SimpleNamespace(text='{"date_label": "Mar 30", "total_assets": 10}')

    models = SimpleNamespace(generate_content=ok)
    llm = GeminiLLM(SimpleNamespace(aio=SimpleNamespace(models=models)))  # type: ignore[arg-type]
    result = await llm.generate_json(model="m", contents=["x"], schema=BalanceSheet)
    assert result.total_assets == 10
