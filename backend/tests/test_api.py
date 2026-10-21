from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.api.uploads import object_name
from app.config import Settings
from app.main import create_app
from tests.conftest import FakeLLM, apple_q2_fy24, parse_sse, text_response

PDF = {"uri": "gs://bucket-15-storage/FY24_Q2_Consolidated_Financial_Statements.pdf",
       "mime_type": "application/pdf"}


def test_health(client: TestClient) -> None:
    health = client.get("/api/health").json()
    assert health == {"status": "ok", "model": "gemini-3.8-flash", "uploads": True, "auth": False}


def test_demo_set_points_at_public_bucket(client: TestClient) -> None:
    demo = client.get("/api/demo").json()
    assert demo["ticker"] == "AAPL"
    marketing = next(a for a in demo["assets"] if a["key"] == "marketing")
    assert marketing["uri"].startswith("gs://bucket-15-storage/")
    assert "%20" in marketing["preview_url"]


def test_statement_stream(client: TestClient, fake_llm: FakeLLM) -> None:
    fake_llm.json_result = apple_q2_fy24()
    resp = client.post("/api/analyses/statement", json={"document": PDF})
    assert resp.status_code == 200
    events = parse_sse(resp.text)
    kinds = [(name, d.get("kind")) for name, d in events]
    assert ("data", "statement") in kinds and ("data", "ratios") in kinds
    assert "".join(d["text"] for n, d in events if n == "delta") == "Hello world"
    assert events[-1][0] == "done"
    extract, commentary = fake_llm.calls
    assert extract["contents"][0].file_data.file_uri == PDF["uri"]
    assert all(isinstance(c, str) for c in commentary["contents"])


def test_statement_requires_pdf(client: TestClient) -> None:
    body = {"document": {**PDF, "mime_type": "image/png"}}
    assert client.post("/api/analyses/statement", json=body).status_code == 415


def test_foreign_media_forbidden(client: TestClient) -> None:
    body = {"document": {**PDF, "uri": "gs://uploads-bucket/uploads/other-user/x/a.pdf"}}
    assert client.post("/api/analyses/statement", json=body).status_code == 403


def test_media_stream(client: TestClient, fake_llm: FakeLLM) -> None:
    body = {
        "media": [{"uri": "gs://bucket-15-storage/output22.mp4", "mime_type": "video/mp4"}],
        "task": "earnings_call",
        "company": "Apple",
    }
    events = parse_sse(client.post("/api/analyses/media", json=body).text)
    assert events[-1][0] == "done"
    parts = fake_llm.calls[0]["contents"]
    assert parts[0].file_data.mime_type == "video/mp4" and "Apple" in parts[1]


def test_market_stream(client: TestClient, fake_llm: FakeLLM) -> None:
    fake_llm.responses = [text_response("Briefing")]
    events = parse_sse(client.post("/api/analyses/market", json={"ticker": "aapl"}).text)
    assert [n for n, _ in events][-2:] == ["delta", "done"]


def test_market_rejects_bad_ticker(client: TestClient) -> None:
    resp = client.post("/api/analyses/market", json={"ticker": "AAPL&x=1"})
    assert resp.status_code == 422


def test_synthesis_falls_back_when_primary_model_missing(
    client: TestClient, fake_llm: FakeLLM, settings: Settings
) -> None:
    fake_llm.failing_models = {settings.model_synthesis}
    body = {"company": "Apple", "sections": {"statement": "Margins up"}}
    events = parse_sse(client.post("/api/analyses/synthesis", json=body).text)
    assert events[-1] == ("done", {"model": settings.model_synthesis_fallback})
    assert [c["model"] for c in fake_llm.calls] == [
        settings.model_synthesis,
        settings.model_synthesis_fallback,
    ]


def test_synthesis_error_event_when_nothing_to_summarize(client: TestClient) -> None:
    body = {"company": "Apple", "sections": {}}
    events = parse_sse(client.post("/api/analyses/synthesis", json=body).text)
    assert events == [("error", {"message": "Run at least one analysis before the synthesis"})]


def test_unexpected_errors_are_not_leaked(client: TestClient, fake_llm: FakeLLM) -> None:
    async def boom(**_: object) -> None:
        raise RuntimeError("secret internal detail")

    fake_llm.generate_json = boom  # type: ignore[method-assign,assignment]
    events = parse_sse(client.post("/api/analyses/statement", json={"document": PDF}).text)
    assert events[-1] == ("error", {"message": "Unexpected server error"})


def test_uploads_need_bucket(settings: Settings, fake_llm: FakeLLM) -> None:
    settings.upload_bucket = ""
    with TestClient(create_app(settings, llm=fake_llm)) as c:
        body = {"filename": "a.pdf", "mime_type": "application/pdf", "size": 10}
        assert c.post("/api/uploads", json=body).status_code == 503


@pytest.mark.parametrize(
    ("body", "code"),
    [
        ({"filename": "a.exe", "mime_type": "application/x-msdownload", "size": 10}, 415),
        ({"filename": "a.mp4", "mime_type": "video/mp4", "size": 10**12}, 413),
    ],
)
def test_upload_validation(client: TestClient, body: dict[str, object], code: int) -> None:
    assert client.post("/api/uploads", json=body).status_code == code


def test_upload_ticket(client: TestClient) -> None:
    with patch("app.api.uploads._sign", return_value="https://signed.example") as sign:
        body = {"filename": "Q2 report.pdf", "mime_type": "application/pdf", "size": 1234}
        ticket = client.post("/api/uploads", json=body).json()
    assert ticket["upload_url"] == "https://signed.example"
    assert ticket["uri"].startswith("gs://uploads-bucket/uploads/dev/")
    assert ticket["headers"]["x-goog-content-length-range"] == "1234,1234"
    assert sign.call_args.args[2] == ticket["headers"]


def test_object_name_is_sanitized() -> None:
    name = object_name("u1", "../../etc/pass wd?.pdf")
    assert name.startswith("uploads/u1/") and ".." not in name and name.endswith("pass_wd_.pdf")


def test_auth_required_rejects_missing_token(settings: Settings, fake_llm: FakeLLM) -> None:
    settings.auth_required = True
    with TestClient(create_app(settings, llm=fake_llm)) as c:
        assert c.post("/api/analyses/statement", json={"document": PDF}).status_code == 401
        assert c.get("/api/demo").status_code == 200


def test_auth_valid_token_scopes_uploads(settings: Settings, fake_llm: FakeLLM) -> None:
    settings.auth_required = True
    with (
        patch("app.api.deps.firebase_admin._apps", {"[DEFAULT]": object()}),
        patch("app.api.deps.fb_auth.verify_id_token", return_value={"uid": "alice"}),
        patch("app.api.uploads._sign", return_value="https://signed.example"),
        TestClient(create_app(settings, llm=fake_llm)) as c,
    ):
        body = {"filename": "a.pdf", "mime_type": "application/pdf", "size": 1}
        resp = c.post("/api/uploads", json=body, headers={"Authorization": "Bearer t"})
    assert resp.json()["uri"].startswith("gs://uploads-bucket/uploads/alice/")
