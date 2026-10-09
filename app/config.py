"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")

APP_NAME = "CreateFlow"
APP_VERSION = "1.0.0"

API_PREFIX = "/api"

# Comma separated list of allowed browser origins.
DEFAULT_CORS_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"

# Uploads / generated assets limits
MAX_LOGO_BYTES = 4 * 1024 * 1024  # 4 MB
MAX_REQUEST_BYTES = 2 * 1024 * 1024  # 2 MB for JSON briefs
ALLOWED_LOGO_MIME = {"image/png", "image/jpeg", "image/svg+xml", "image/webp"}
ALLOWED_LOGO_EXT = {".png", ".jpg", ".jpeg", ".svg", ".webp"}

SUPABASE_STORAGE_BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET", "createflow-assets")
SIGNED_URL_TTL_SECONDS = int(os.getenv("SUPABASE_SIGNED_URL_TTL", "900"))


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


@lru_cache
def get_settings() -> dict:
    """Return the runtime settings snapshot.

    Cloud credentials are optional. When they are absent the API runs in an
    explicit "local development" mode where generated files are returned from
    the local temporary workspace and nothing is reported as cloud-saved.
    """
    frontend_dir = BACKEND_DIR.parent / "frontend" / "dist"
    return {
        "app_name": APP_NAME,
        "version": APP_VERSION,
        "cors_origins": [
            origin.strip()
            for origin in os.getenv("CORS_ORIGINS", DEFAULT_CORS_ORIGINS).split(",")
            if origin.strip()
        ],
        "supabase_url": _clean(os.getenv("SUPABASE_URL")),
        "supabase_anon_key": _clean(os.getenv("SUPABASE_ANON_KEY")),
        "supabase_service_role_key": _clean(os.getenv("SUPABASE_SERVICE_ROLE_KEY")),
        "supabase_storage_bucket": SUPABASE_STORAGE_BUCKET,
        "signed_url_ttl": SIGNED_URL_TTL_SECONDS,
        "frontend_dist": frontend_dir,
        "temp_root": Path(os.getenv("CREATEFLOW_TEMP_DIR", BACKEND_DIR / ".tmp")),
    }


def cloud_configured() -> bool:
    s = get_settings()
    return bool(s["supabase_url"] and s["supabase_service_role_key"])