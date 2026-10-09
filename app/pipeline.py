"""Generation pipeline: brief -> files -> optional cloud records.

Temporary files are created inside a dedicated temp root and removed as soon as
they are uploaded (cloud mode) or served (local development mode).
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import logging
import shutil
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from PIL import Image, ImageOps

from .config import (
    ALLOWED_LOGO_EXT,
    ALLOWED_LOGO_MIME,
    MAX_LOGO_BYTES,
    get_settings,
)
from .content import build_outline
from .design import build_design_system, safe_filename
from .graphics import available_fonts, render_poster, render_social, render_svg
from .pptx_engine import build_deck
from .schemas import AssetKind, GenerateRequest

log = logging.getLogger("createflow.pipeline")

LOCAL_TTL_SECONDS = 60 * 60  # local dev downloads expire after one hour


class LogoError(ValueError):
    pass


@dataclass
class GeneratedAsset:
    kind: AssetKind
    filename: str
    path: Path
    content_type: str
    width: Optional[int] = None
    height: Optional[int] = None

    @property
    def size(self) -> int:
        return self.path.stat().st_size

    @property
    def checksum(self) -> str:
        digest = hashlib.sha256()
        with self.path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def to_out(self, download_url: Optional[str] = None, storage_path: Optional[str] = None,
               cloud_saved: bool = False, asset_id: Optional[str] = None) -> dict:
        return {
            "id": asset_id,
            "kind": self.kind.value,
            "filename": self.filename,
            "content_type": self.content_type,
            "size_bytes": self.size,
            "width": self.width,
            "height": self.height,
            "download_url": download_url,
            "storage_path": storage_path,
            "cloud_saved": cloud_saved,
            "checksum": self.checksum,
        }


@dataclass
class GenerationResult:
    slide_count: int
    design: object
    layouts: list[str]
    assets: list[GeneratedAsset]
    workspace: Path
    token: str
    notes: list[str] = field(default_factory=list)
    outline_titles: list[str] = field(default_factory=list)

    def cleanup(self) -> None:
        shutil.rmtree(self.workspace, ignore_errors=True)


def temp_root() -> Path:
    root = get_settings()["temp_root"]
    root.mkdir(parents=True, exist_ok=True)
    return root


def purge_stale_workspaces(max_age_seconds: int = LOCAL_TTL_SECONDS) -> int:
    """Remove orphaned temp workspaces so failures never leak files."""
    root = temp_root()
    removed = 0
    now = time.time()
    try:
        for entry in root.iterdir():
            if not entry.is_dir():
                continue
            try:
                if now - entry.stat().st_mtime > max_age_seconds:
                    shutil.rmtree(entry, ignore_errors=True)
                    removed += 1
            except OSError:
                continue
    except OSError:
        pass
    return removed


# --------------------------------------------------------------------------
# logo validation
# --------------------------------------------------------------------------
def decode_logo(data_url: str) -> bytes:
    """Validate and decode a ``data:`` URL logo. Raises :class:`LogoError`."""
    if not data_url or "," not in data_url:
        raise LogoError("Logo must be a base64 data URL.")
    header, payload = data_url.split(",", 1)
    if not header.startswith("data:"):
        raise LogoError("Logo must be a base64 data URL.")
    parts = header[5:].split(";")
    mime = parts[0].strip().lower()
    if mime not in ALLOWED_LOGO_MIME:
        raise LogoError(f"Unsupported logo type '{mime}'. Allowed: {', '.join(sorted(ALLOWED_LOGO_MIME))}.")
    ext = Path(parts[-1]).suffix.lower()
    if ext not in ALLOWED_LOGO_EXT:
        raise LogoError(f"Unsupported logo extension '{ext}'.")

    try:
        raw = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise LogoError("Logo data is not valid base64.") from exc
    if not raw:
        raise LogoError("Logo data is empty.")
    if len(raw) > MAX_LOGO_BYTES:
        raise LogoError(f"Logo exceeds the {MAX_LOGO_BYTES // (1024 * 1024)} MB limit.")

    if mime == "image/svg+xml":
        text = raw.decode("utf-8", errors="ignore").lower()
        if "<script" in text or "javascript:" in text or "onload=" in text:
            raise LogoError("SVG logo contains disallowed script content.")
        return raw

    try:
        import io

        with Image.open(io.BytesIO(raw)) as probe:
            probe.verify()
        with Image.open(io.BytesIO(raw)) as img:
            img.load()
            fmt = (img.format or "").lower()
            if fmt not in {"png", "jpeg", "webp"}:
                raise LogoError(f"Unsupported logo image format '{fmt}'.")
            img = ImageOps.exif_transpose(img)
            out = __import__("io").BytesIO()
            img.convert("RGBA").save(out, format="PNG")
            return out.getvalue()
    except LogoError:
        raise
    except Exception as exc:
        raise LogoError("Logo image could not be decoded.") from exc


# --------------------------------------------------------------------------
# main pipeline
# --------------------------------------------------------------------------
def generate(brief: GenerateRequest, *, keep_workspace: bool = True) -> GenerationResult:
    """Render all assets for ``brief`` into a private temp workspace."""
    workspace = temp_root() / uuid.uuid4().hex
    workspace.mkdir(parents=True, exist_ok=True)
    notes: list[str] = []

    design = build_design_system(brief)
    outline = build_outline(brief)

    if brief.logo_data_url:
        try:
            raw = decode_logo(brief.logo_data_url)
            (workspace / "brand-logo.png").write_bytes(raw)
            notes.append("Brand logo accepted and stored with the generation workspace.")
        except LogoError as exc:
            notes.append(f"Logo rejected and skipped: {exc}")

    if brief.presentation_type.value == "report":
        notes.append(
            "Report mode keeps figure labelling strict: any non-provided numbers are marked "
            "illustrative on the slide itself."
        )

    base = safe_filename(brief.project_name)
    brand = safe_filename(design.brand_name, 32)

    deck_path = workspace / f"{base}-presentation.pptx"
    slide_count, design, layouts = build_deck(brief, deck_path)
    log.info("deck built: %s slides -> %s", slide_count, deck_path.name)

    poster_path = workspace / f"{brand}-poster.png"
    poster_meta = render_poster(design, brief=brief, out_path=poster_path)
    log.info("poster rendered: %sx%s", poster_meta["width"], poster_meta["height"])

    social_path = workspace / f"{brand}-social.png"
    social_meta = render_social(design, brief=brief, out_path=social_path)
    log.info("social rendered: %sx%s", social_meta["width"], social_meta["height"])

    svg_path = workspace / f"{brand}-mark.svg"
    svg_meta = render_svg(design, brief=brief, out_path=svg_path)

    assets = [
        GeneratedAsset(AssetKind.PRESENTATION, deck_path.name, deck_path,
                       "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
        GeneratedAsset(AssetKind.POSTER, poster_path.name, poster_path,
                       poster_meta["content_type"], poster_meta["width"], poster_meta["height"]),
        GeneratedAsset(AssetKind.SOCIAL, social_path.name, social_path,
                       social_meta["content_type"], social_meta["width"], social_meta["height"]),
        GeneratedAsset(AssetKind.SVG, svg_path.name, svg_path, svg_meta["content_type"],
                       svg_meta["width"], svg_meta["height"]),
    ]

    fonts = available_fonts()
    if not fonts:
        notes.append("No bundled display fonts were detected; Pillow default metrics were used.")

    if not keep_workspace:
        result = GenerationResult(slide_count, design, layouts, assets, workspace,
                                  uuid.uuid4().hex, notes, [s.title for s in outline])
        result.cleanup()
        raise RuntimeError("workspace removed before serving")

    return GenerationResult(
        slide_count=slide_count,
        design=design,
        layouts=layouts,
        assets=assets,
        workspace=workspace,
        token=uuid.uuid4().hex,
        notes=notes,
        outline_titles=[s.title for s in outline],
    )