import re
import uuid
from datetime import timedelta

import google.auth
from fastapi import APIRouter, HTTPException, status
from google.auth.transport.requests import Request as AuthRequest
from google.cloud import storage
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app.analyses.common import SUPPORTED_MIME_PREFIXES
from app.api.deps import SettingsDep, UserDep
from app.config import Settings

router = APIRouter(prefix="/api/uploads", tags=["uploads"])


class UploadRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=200)
    mime_type: str
    size: int = Field(gt=0)


class UploadTicket(BaseModel):
    upload_url: str
    uri: str
    mime_type: str
    headers: dict[str, str]


def upload_headers(mime_type: str, size: int) -> dict[str, str]:
    return {"Content-Type": mime_type, "x-goog-content-length-range": f"{size},{size}"}


def object_name(user_id: str, filename: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", filename).strip("._") or "file"
    return f"uploads/{user_id}/{uuid.uuid4().hex}/{safe[:100]}"


def _sign(settings: Settings, name: str, headers: dict[str, str]) -> str:
    credentials, project = google.auth.default()
    credentials.refresh(AuthRequest())  # type: ignore[no-untyped-call]
    blob = storage.Client(project=project, credentials=credentials).bucket(
        settings.upload_bucket
    ).blob(name)
    url: str = blob.generate_signed_url(
        version="v4",
        expiration=timedelta(minutes=15),
        method="PUT",
        headers=headers,
        service_account_email=getattr(credentials, "service_account_email", None),
        access_token=credentials.token,
    )
    return url


@router.post("", response_model=UploadTicket)
async def create_upload(body: UploadRequest, settings: SettingsDep, user: UserDep) -> UploadTicket:
    if not settings.upload_bucket:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Uploads are not configured")
    if not body.mime_type.startswith(SUPPORTED_MIME_PREFIXES):
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Unsupported file type")
    if body.size > settings.upload_max_bytes:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "File is too large")
    name = object_name(user, body.filename)
    headers = upload_headers(body.mime_type, body.size)
    url = await run_in_threadpool(_sign, settings, name, headers)
    return UploadTicket(
        upload_url=url,
        uri=f"gs://{settings.upload_bucket}/{name}",
        mime_type=body.mime_type,
        headers=headers,
    )
