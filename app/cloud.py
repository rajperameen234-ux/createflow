"""Supabase access layer.

Everything here is optional at runtime. If credentials are absent the API
serves clearly-labelled local development results; if a call fails after the
credentials exist, the failure is surfaced honestly rather than swallowed.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from .config import get_settings

log = logging.getLogger("createflow.storage")

MISSING_CONFIG_MESSAGE = (
    "Supabase is not configured on this server. Add SUPABASE_URL and "
    "SUPABASE_SERVICE_ROLE_KEY to backend/.env to enable cloud saving."
)


@dataclass
class CloudResult:
    saved: bool
    mode: str
    message: str
    project_id: Optional[str] = None


def _normalise_user(raw) -> dict:
    """Flatten supabase-py's user object into a plain dict.

    ``auth.get_user()`` returns a ``UserResponse`` that wraps the real ``User``
    under a ``user`` attribute, so ``dict(response)`` yields ``{"user": User(...)}``.
    Reading ``.get("id")`` straight off that returns ``None`` and every
    ownership filter would silently compare against the string "None".
    """
    if raw is None:
        return {}
    inner = getattr(raw, "user", None)
    if inner is not None and not isinstance(inner, dict):
        return {
            "id": getattr(inner, "id", None),
            "email": getattr(inner, "email", None),
            "role": getattr(inner, "role", None),
        }
    data = raw if isinstance(raw, dict) else {}
    nested = data.get("user")
    if nested is not None:
        if isinstance(nested, dict):
            return {"id": nested.get("id"), "email": nested.get("email")}
        return {
            "id": getattr(nested, "id", None),
            "email": getattr(nested, "email", None),
        }
    return {
        "id": data.get("id") or getattr(raw, "id", None),
        "email": data.get("email") or getattr(raw, "email", None),
    }


class CloudClient:
    """Thin wrapper around supabase-py with explicit failure reporting."""

    def __init__(self) -> None:
        settings = get_settings()
        self.url = settings["supabase_url"]
        self.service_key = settings["supabase_service_role_key"]
        self.anon_key = settings["supabase_anon_key"]
        self.bucket = settings["supabase_storage_bucket"]
        self.ttl = settings["signed_url_ttl"]
        self._client = None
        self._error: Optional[str] = None

    # -- lifecycle -------------------------------------------------------
    @property
    def configured(self) -> bool:
        return bool(self.url and self.service_key)

    @property
    def error(self) -> Optional[str]:
        return self._error

    def client(self):
        if not self.configured:
            raise RuntimeError(MISSING_CONFIG_MESSAGE)
        if self._client is None:
            try:
                from supabase import create_client

                self._client = create_client(self.url, self.service_key)
            except Exception as exc:  # pragma: no cover - import/runtime guard
                self._error = f"Supabase client init failed: {exc}"
                log.error("supabase client init failed: %s", exc)
                raise RuntimeError(self._error) from exc
        return self._client

    # -- reads -----------------------------------------------------------
    def verify_token(self, token: str) -> Optional[dict]:
        """Resolve a Supabase access token to a user dict. Never raises."""
        if not token or not self.url or not (self.service_key or self.anon_key):
            self._error = MISSING_CONFIG_MESSAGE
            return None
        key = self.service_key or self.anon_key
        try:
            from supabase import create_client

            anon = create_client(self.url, key)
            user = anon.auth.get_user(token)
            record = _normalise_user(user)
            return record or None
        except Exception as exc:
            self._error = f"Token verification failed: {exc}"
            log.warning("token verification failed: %s", exc)
            return None

    def list_projects(self, user_id: str) -> list[dict]:
        res = (
            self.client()
            .table("projects")
            .select("*, generated_assets(*)")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        return list(res.data or [])

    def get_project(self, project_id: str, user_id: str) -> Optional[dict]:
        res = (
            self.client()
            .table("projects")
            .select("*, generated_assets(*)")
            .eq("id", project_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        rows = list(res.data or [])
        return rows[0] if rows else None

    def delete_project(self, project_id: str, user_id: str) -> tuple[bool, int]:
        project = self.get_project(project_id, user_id)
        if not project:
            return False, 0
        paths = [a["storage_path"] for a in (project.get("generated_assets") or [])
                 if a.get("storage_path")]
        removed = 0
        if paths:
            try:
                self.client().storage.from_(self.bucket).remove(paths)
                removed = len(paths)
            except Exception as exc:
                log.warning("storage removal failed for %s: %s", project_id, exc)
        self.client().table("projects").delete().eq("id", project_id).eq("user_id", user_id).execute()
        return True, removed

    # -- writes ----------------------------------------------------------
    def create_project(self, user_id: str, payload: dict) -> str:
        project_id = str(uuid.uuid4())
        row = {"id": project_id, "user_id": user_id, **payload}
        self.client().table("projects").insert(row).execute()
        return project_id

    def update_project_brief(self, project_id: str, user_id: str, patch: dict) -> bool:
        res = (
            self.client()
            .table("projects")
            .update(patch)
            .eq("id", project_id)
            .eq("user_id", user_id)
            .execute()
        )
        return bool(res.data)

    def replace_assets(self, project_id: str, user_id: str, assets: list[dict]) -> None:
        """Delete previous asset rows and storage objects, then insert new ones."""
        existing = self.get_project(project_id, user_id) or {}
        old_paths = [a["storage_path"] for a in (existing.get("generated_assets") or [])
                     if a.get("storage_path")]
        if old_paths:
            try:
                self.client().storage.from_(self.bucket).remove(old_paths)
            except Exception as exc:
                log.warning("old asset removal failed for %s: %s", project_id, exc)
        self.client().table("generated_assets").delete().eq("project_id", project_id).execute()
        if assets:
            self.client().table("generated_assets").insert(assets).execute()

    def upload_asset(self, project_id: str, user_id: str, filename: str, data: bytes,
                     content_type: str) -> str:
        path = f"{user_id}/{project_id}/{filename}"
        # storage3 lifts these into HTTP headers verbatim, so the keys must be
        # hyphenated and every value a string.
        self.client().storage.from_(self.bucket).upload(
            path, data, {"content-type": content_type, "upsert": "true"}
        )
        return path

    def remove_objects(self, paths: list[str]) -> int:
        """Delete storage objects by path, tolerating ones that never landed."""
        if not paths:
            return 0
        removed = 0
        for path in paths:
            try:
                self.client().storage.from_(self.bucket).remove([path])
                removed += 1
            except Exception as exc:
                log.warning("could not remove %s: %s", path, exc)
        return removed

    def signed_url(self, path: str) -> Optional[str]:
        try:
            res = self.client().storage.from_(self.bucket).create_signed_url(path, self.ttl)
            return (res or {}).get("signedURL") or (res or {}).get("signed_url")
        except Exception as exc:
            log.warning("signed url failed for %s: %s", path, exc)
            return None

    # -- diagnostics -----------------------------------------------------
    def probe(self) -> dict[str, Any]:
        if not self.configured:
            return {"configured": False, "reachable": False, "message": MISSING_CONFIG_MESSAGE}
        try:
            self.client().table("projects").select("id", count="exact").limit(1).execute()
            return {"configured": True, "reachable": True, "message": "Supabase reachable."}
        except Exception as exc:
            return {
                "configured": True,
                "reachable": False,
                "message": f"Supabase configured but not reachable: {exc}",
            }


_cloud: Optional[CloudClient] = None


def get_cloud() -> CloudClient:
    global _cloud
    if _cloud is None:
        _cloud = CloudClient()
    return _cloud


SCHEMA_NOT_READY_HINT = (
    "The database schema is not applied yet. Open your Supabase project -> SQL Editor, "
    "paste supabase/migrations/0001_createflow_schema.sql and press Run."
)


def is_schema_missing(error: Exception) -> bool:
    """True when PostgREST reports a missing table, i.e. the migration is unapplied."""
    text = str(error).lower()
    return (
        "pgrst205" in text
        or "could not find the table" in text
        or "does not exist" in text and "relation" in text
    )


def reset_cloud() -> None:
    global _cloud
    _cloud = None


def project_payload(brief, design, slide_count: int, layout_labels: list[str]) -> dict:
    """Map a brief + design system onto the ``projects`` table columns."""
    return {
        "project_name": brief.project_name,
        "topic": brief.topic,
        "audience": brief.audience,
        "goal": brief.goal,
        "tone": brief.tone,
        "presentation_type": brief.presentation_type.value,
        "presentation_length": brief.presentation_length,
        "slide_count": slide_count,
        "visual_style": brief.visual_style,
        "style_preset": brief.style_preset.value,
        "primary_color": design.primary,
        "secondary_color": design.secondary,
        "accent_color": design.accent,
        "brand_name": design.brand_name,
        "tagline": design.tagline,
        "extra_instructions": brief.extra_instructions,
        "brief_json": brief.model_dump(mode="json"),
        "layouts_json": layout_labels,
        "status": "ready",
    }


def asset_row(project_id: str, user_id: str, asset: dict, storage_path: str,
              checksum: str) -> dict:
    # user_id is NOT NULL in the schema and is what RLS scopes rows by, so it
    # must be written explicitly on every asset row.
    return {
        "id": str(uuid.uuid4()),
        "project_id": project_id,
        "user_id": user_id,
        "kind": asset["kind"],
        "filename": asset["filename"],
        "storage_path": storage_path,
        "content_type": asset["content_type"],
        "size_bytes": asset["size_bytes"],
        "width_px": asset.get("width"),
        "height_px": asset.get("height"),
        "checksum": checksum,
    }


def read_bytes(path: Path) -> bytes:
    return Path(path).read_bytes()