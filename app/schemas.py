"""Validated request/response schemas for the CreateFlow API."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class PresentationType(str, Enum):
    EDUCATIONAL = "educational"
    BUSINESS_PITCH = "business_pitch"
    MARKETING = "marketing"
    PORTFOLIO = "portfolio"
    REPORT = "report"


class StylePreset(str, Enum):
    EDITORIAL_LUXURY = "editorial_luxury"
    MODERN_MINIMAL = "modern_minimal"
    BOLD_CREATIVE = "bold_creative"
    CORPORATE_PREMIUM = "corporate_premium"
    DARK_CINEMATIC = "dark_cinematic"
    PLAYFUL_COLORFUL = "playful_colorful"


HEX_RE = r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$"


def _validate_hex(value: str, field: str) -> str:
    import re

    if not re.match(HEX_RE, value.strip()):
        raise ValueError(f"{field} must be a hex colour such as #4B2E23")
    return value.strip().upper()


class GenerateRequest(BaseModel):
    """A single creative brief."""

    project_name: str = Field(min_length=2, max_length=90)
    topic: str = Field(min_length=10, max_length=1200)
    audience: str = Field(min_length=3, max_length=400)
    goal: str = Field(min_length=3, max_length=400)
    tone: str = Field(min_length=3, max_length=200)
    presentation_length: int = Field(default=8, ge=5, le=16)
    presentation_type: PresentationType = PresentationType.MARKETING
    visual_style: str = Field(default="Editorial luxury", max_length=120)
    style_preset: StylePreset = StylePreset.EDITORIAL_LUXURY
    primary_color: str = Field(default="#3A2418", max_length=7)
    secondary_color: str = Field(default="#E8DCC8", max_length=7)
    accent_color: Optional[str] = Field(default=None, max_length=7)
    brand_name: str = Field(default="", max_length=90)
    tagline: str = Field(default="", max_length=160)
    extra_instructions: str = Field(default="", max_length=2000)
    logo_data_url: Optional[str] = Field(default=None, max_length=6_000_000)

    @field_validator("primary_color", "secondary_color")
    @classmethod
    def _check_required_hex(cls, v: str) -> str:
        return _validate_hex(v, "colour")

    @field_validator("accent_color")
    @classmethod
    def _check_optional_hex(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return _validate_hex(v, "accent_color")

    @field_validator("project_name", "topic", "audience", "goal", "tone")
    @classmethod
    def _strip(cls, v: str) -> str:
        cleaned = " ".join(v.split())
        if len(cleaned) < 2:
            raise ValueError("value must contain at least two non-space characters")
        return cleaned


class AssetKind(str, Enum):
    PRESENTATION = "presentation"
    POSTER = "poster"
    SOCIAL = "social"
    SVG = "svg"


class AssetOut(BaseModel):
    id: Optional[str] = None
    kind: AssetKind
    filename: str
    content_type: str
    size_bytes: int
    width: Optional[int] = None
    height: Optional[int] = None
    download_url: Optional[str] = None
    storage_path: Optional[str] = None
    cloud_saved: bool = False
    checksum: Optional[str] = None


class GenerateResponse(BaseModel):
    project_id: Optional[str] = None
    cloud_saved: bool
    cloud_mode: str = Field(description="cloud | local-development")
    cloud_message: str
    theme: "ThemeSummary"
    slide_count: int
    assets: list[AssetOut]
    notes: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now())


class ThemeSummary(BaseModel):
    preset: StylePreset
    preset_label: str
    primary_color: str
    secondary_color: str
    accent_color: str
    ink: str
    paper: str
    heading_font: str
    body_font: str
    motif: str


class ProjectSummary(BaseModel):
    id: str
    project_name: str
    topic: str
    style_preset: StylePreset
    primary_color: str
    secondary_color: str
    brand_name: str
    tagline: str
    slide_count: int
    asset_count: int
    created_at: datetime
    updated_at: Optional[datetime] = None


class ProjectDetail(ProjectSummary):
    goal: str
    audience: str
    tone: str
    presentation_type: PresentationType
    visual_style: str
    extra_instructions: str
    brief: dict
    assets: list[AssetOut]


class DeleteResponse(BaseModel):
    deleted: bool
    project_id: str
    storage_objects_removed: int = 0
    message: str


class HealthResponse(BaseModel):
    status: str
    version: str
    cloud_configured: bool
    cloud_message: str
    auth_required: bool
    fonts: list[str]
    slide_layouts: list[str]
    capabilities: dict