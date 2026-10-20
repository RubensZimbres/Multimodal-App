"""The original Apple Q2 FY24 case, kept as a one-click demo set."""

from urllib.parse import quote

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import SettingsDep

router = APIRouter(prefix="/api/demo", tags=["demo"])


class DemoAsset(BaseModel):
    key: str
    title: str
    uri: str
    mime_type: str
    preview_url: str


class DemoSet(BaseModel):
    company: str
    ticker: str
    assets: list[DemoAsset]


_ASSETS = [
    ("statement", "FY24 Q2 consolidated financial statements",
     "FY24_Q2_Consolidated_Financial_Statements.pdf", "application/pdf"),
    ("pricing", "Apple product prices across 26 countries", "pricing.jpeg", "image/jpeg"),
    ("earnings_call", "Q2 2024 earnings call excerpt", "output22.mp4", "video/mp4"),
    ("marketing", "Introducing iPhone 15 Pro", "Introducing iPhone 15 Pro Apple.mp4", "video/mp4"),
]


@router.get("", response_model=DemoSet)
async def demo_set(settings: SettingsDep) -> DemoSet:
    prefix = settings.demo_media_prefix
    bucket_path = prefix.removeprefix("gs://")
    return DemoSet(
        company="Apple Inc.",
        ticker="AAPL",
        assets=[
            DemoAsset(
                key=key,
                title=title,
                uri=f"{prefix}{name}",
                mime_type=mime,
                preview_url=f"https://storage.googleapis.com/{bucket_path}{quote(name)}",
            )
            for key, title, name, mime in _ASSETS
        ],
    )
