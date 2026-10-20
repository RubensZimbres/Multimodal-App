import pytest

from app.analyses.common import MediaNotAllowed, MediaRef, check_media
from app.analyses.media import MediaTask, build_prompt
from app.analyses.statement import commentary_prompt
from app.analyses.synthesis import SynthesisInput
from app.analyses.synthesis import build_prompt as synthesis_prompt
from app.config import Settings
from app.finance.ratios import compute_ratios
from tests.conftest import apple_q2_fy24


@pytest.mark.parametrize(
    "uri",
    [
        "gs://bucket-15-storage/pricing.jpeg",
        "gs://uploads-bucket/uploads/alice/abc/report.pdf",
    ],
)
def test_allowed_media(settings: Settings, uri: str) -> None:
    check_media(MediaRef(uri=uri, mime_type="application/pdf"), "alice", settings)


@pytest.mark.parametrize(
    ("uri", "mime"),
    [
        ("gs://uploads-bucket/uploads/bob/abc/report.pdf", "application/pdf"),  # other user
        ("gs://uploads-bucket/secrets/key.json", "application/pdf"),
        ("gs://someone-elses-bucket/file.pdf", "application/pdf"),
        ("gs://uploads-bucket/uploads/alice/../bob/x.pdf", "application/pdf"),
        ("gs://bucket-15-storage/pricing.jpeg", "text/html"),
    ],
)
def test_rejected_media(settings: Settings, uri: str, mime: str) -> None:
    with pytest.raises(MediaNotAllowed):
        check_media(MediaRef(uri=uri, mime_type=mime), "alice", settings)


def test_media_presets_include_company_and_extra_question() -> None:
    prompt = build_prompt(MediaTask.MARKETING, "Acme", "Who is the target audience?")
    assert "Acme" in prompt and prompt.endswith("Who is the target audience?")


def test_custom_media_task_requires_question() -> None:
    with pytest.raises(ValueError, match="question"):
        build_prompt(MediaTask.CUSTOM, "Acme", None)


def test_commentary_prompt_carries_computed_numbers() -> None:
    s = apple_q2_fy24()
    prompt = commentary_prompt(s, compute_ratios(s))
    assert "Apple Inc." in prompt and "46.578" in prompt and "do not recalculate" in prompt


def test_synthesis_prompt_lists_missing_sections() -> None:
    prompt = synthesis_prompt(
        SynthesisInput(company="Apple", sections={"statement": "Margins up", "bogus": "x"})
    )
    assert '<section name="statement"' in prompt
    assert "bogus" not in prompt
    assert "Marketing campaign" in prompt.split("were not run")[1]


def test_synthesis_requires_some_input() -> None:
    with pytest.raises(ValueError, match="at least one"):
        synthesis_prompt(SynthesisInput(company="Apple", sections={"market": "  "}))
