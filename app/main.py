"""CreateFlow API.

Public endpoints:  /api/health, /api/presets, /api/preview
Protected:        /api/generate, /api/projects, /api/projects/{id}, /api/download/*
"""

from __future__ import annotations

import logging
import mimetypes
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from .auth import Identity, optional_user, require_user
from .cloud import (
    SCHEMA_NOT_READY_HINT,
    CloudResult,
    asset_row,
    get_cloud,
    is_schema_missing,
    project_payload,
)
from .config import API_PREFIX, APP_VERSION, get_settings
from .content import build_outline, headline_from
from .design import STYLE_PRESETS, build_design_system, swatch_palette
from .graphics import available_fonts
from .pipeline import LogoError, generate, purge_stale_workspaces
from .pptx_engine import LAYOUTS
from .slide_preview import cached_slide_png, contact_sheet_png
from .schemas import (
    DeleteResponse,
    GenerateRequest,
    GenerateResponse,
    HealthResponse,
    PresentationType,
    ProjectDetail,
    ProjectSummary,
    StylePreset,
    ThemeSummary,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
)
log = logging.getLogger("createflow.api")

START_TIME = time.time()

# Local development results, keyed by an unguessable token. Cleared on restart
# and on any successful cloud upload. Never presented as persisted.
_LOCAL_RESULTS: dict[str, tuple[float, dict]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings["temp_root"].mkdir(parents=True, exist_ok=True)
    removed = purge_stale_workspaces()
    log.info(
        "startup: cloud_configured=%s stale_workspaces_removed=%s",
        bool(settings["supabase_url"] and settings["supabase_service_role_key"]),
        removed,
    )
    yield
    _LOCAL_RESULTS.clear()
    log.info("shutdown complete")


app = FastAPI(
    title="CreateFlow API",
    version=APP_VERSION,
    description=(
        "Turns a single creative brief into an editable PowerPoint deck, a poster and a "
        "square social graphic that share one visual identity."
    ),
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings["cors_origins"],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    max_age=600,
)


@app.middleware("http")
async def request_guard(request: Request, call_next):
    if request.method in ("POST", "PUT", "PATCH"):
        length = request.headers.get("content-length")
        if length and length.isdigit() and int(length) > 8 * 1024 * 1024:
            return JSONResponse(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                content={"detail": "Request body exceeds the 8 MB limit."},
            )
    return await call_next(request)


def _field_problems(errors) -> list[dict]:
    problems = []
    for err in errors:
        loc = [str(p) for p in err.get("loc", ()) if p not in ("body", "query", "path")]
        problems.append({
            "field": ".".join(loc) or "body",
            "message": err.get("msg", "invalid value"),
        })
    return problems


@app.exception_handler(RequestValidationError)
async def request_validation_handler(request: Request, exc: RequestValidationError):
    """Return field-level problems so the UI can highlight the right inputs."""
    return JSONResponse(
        status_code=422,
        content={"detail": _field_problems(exc.errors())},
    )


def _schema_failure(exc: Exception):
    """Translate a missing-schema error into an actionable 503."""
    if is_schema_missing(exc):
        return HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"Supabase is reachable but the CreateFlow tables do not exist yet. "
            f"{SCHEMA_NOT_READY_HINT}",
        )
    return None


@app.exception_handler(ValidationError)
async def validation_handler(request: Request, exc: ValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": _field_problems(exc.errors())},
    )


# --------------------------------------------------------------------------
# public
# --------------------------------------------------------------------------
@app.get(f"{API_PREFIX}/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    cloud = get_cloud()
    configured = cloud.configured
    probe = cloud.probe() if configured else {"configured": False, "reachable": False,
                                              "message": "Supabase credentials are not set."}
    if configured and probe["reachable"]:
        message = "Supabase configured and reachable."
    elif configured:
        message = probe["message"]
    else:
        message = (
            "Supabase is not configured. Generation works locally; projects, downloads and "
            "cloud saving are disabled."
        )
    return HealthResponse(
        status="ok",
        version=APP_VERSION,
        cloud_configured=configured and bool(probe["reachable"]),
        cloud_message=message,
        auth_required=configured,
        fonts=available_fonts()[:12],
        slide_layouts=sorted(LAYOUTS.keys()),
        capabilities={
            "pptx_editable": True,
            "poster_png": True,
            "social_png": True,
            "svg_mark": True,
            "charts": ["column", "bar", "line", "doughnut"],
            "speaker_notes": True,
            "cloud_persistence": bool(configured and probe["reachable"]),
            "local_generation": True,
        },
    )


@app.get(f"{API_PREFIX}/presets", tags=["design"])
def presets() -> dict:
    items = []
    for key, spec in STYLE_PRESETS.items():
        items.append({
            "id": key.value,
            "label": spec.label,
            "description": spec.description,
            "motif": spec.motif,
            "heading_font": spec.heading_font,
            "body_font": spec.body_font,
            "dark_canvas": spec.dark_canvas,
            "default_primary": spec.default_primary,
            "default_secondary": spec.default_secondary,
            "default_accent": spec.default_accent,
            "paper": spec.paper,
            "ink": spec.ink,
            "swatch": swatch_palette(spec.default_primary, spec.default_secondary,
                                     spec.default_accent, spec.dark_canvas),
        })
    return {
        "presets": items,
        "presentation_types": [t.value for t in PresentationType],
        "layouts": sorted(LAYOUTS.keys()),
    }


@app.post(f"{API_PREFIX}/preview", tags=["design"])
def preview(brief: GenerateRequest) -> dict:
    """Instant theme + outline preview. Runs the real engines, writes no files."""
    started = time.perf_counter()
    design = build_design_system(brief)
    outline = build_outline(brief)
    return {
        "theme": design.summary(),
        "swatch": swatch_palette(design.primary, design.secondary, design.accent,
                                 design.dark_canvas),
        "slides": [
            {"n": i + 1, "layout": s.layout, "title": s.title, "kicker": s.kicker}
            for i, s in enumerate(outline)
        ],
        "slide_count": len(outline),
        "headline": headline_from(brief.topic, brief.project_name, 40),
        "elapsed_ms": int((time.perf_counter() - started) * 1000),
    }


# --------------------------------------------------------------------------
# generation
# --------------------------------------------------------------------------
@app.post(f"{API_PREFIX}/generate", response_model=GenerateResponse, tags=["generation"])
def create_package(
    brief: GenerateRequest,
    response: Request,
    identity: Optional[Identity] = Depends(optional_user),
) -> GenerateResponse:
    """Generate the full creative package for ``brief``.

    When an authenticated user is present and Supabase is configured, files are
    uploaded to private storage and metadata written to Postgres. Otherwise the
    response is explicitly labelled ``local-development`` and served from a
    temporary workspace that expires within an hour.
    """
    if len(brief.topic) < 10:
        raise HTTPException(422, "Topic must describe the brief in at least 10 characters.")

    started = time.perf_counter()
    try:
        result = generate(brief)
    except LogoError as exc:
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:  # pragma: no cover - surfaced to the client honestly
        log.exception("generation failed")
        raise HTTPException(500, f"Generation failed: {exc}") from exc

    elapsed = time.perf_counter() - started
    log.info("generated %s assets in %.2fs", len(result.assets), elapsed)

    cloud = get_cloud()
    cloud_outcome = CloudResult(
        saved=False,
        mode="local-development",
        message=(
            "Generated locally and available for download for one hour. "
            "Nothing was saved to the cloud because no authenticated Supabase session was supplied."
            if not cloud.configured or identity is None
            else "Cloud saving was not attempted because no authenticated session was supplied."
        ),
    )
    project_id: Optional[str] = None
    assets_out: list[dict] = []

    if identity and cloud.configured:
        try:
            project_id = cloud.create_project(identity.id, project_payload(
                brief, result.design, result.slide_count, result.layouts
            ))
            rows = []
            uploaded_paths: list[str] = []
            for asset in result.assets:
                data = asset.path.read_bytes()
                path = cloud.upload_asset(project_id, identity.id, asset.filename, data,
                                          asset.content_type)
                uploaded_paths.append(path)
                row = asset_row(project_id, identity.id, asset.to_out(storage_path=path),
                                path, asset.checksum)
                rows.append(row)
            cloud.replace_assets(project_id, identity.id, rows)
            assets_out = [
                asset.to_out(
                    download_url=cloud.signed_url(row["storage_path"]),
                    storage_path=row["storage_path"],
                    cloud_saved=True,
                    asset_id=row["id"],
                )
                for asset, row in zip(result.assets, rows)
            ]
            _LOCAL_RESULTS.pop(result.token, None)
            cloud_outcome = CloudResult(
                saved=True,
                mode="cloud",
                message=f"Saved to Supabase as project {project_id}.",
                project_id=project_id,
            )
        except Exception as exc:
            log.exception("cloud save failed")
            cloud_outcome = CloudResult(
                saved=False,
                mode="cloud-error",
                message=(
                    "Generation succeeded but the cloud save failed, so nothing is marked as saved. "
                    f"Reason: {exc}"
                ),
                project_id=project_id,
            )
            # Roll back completely: the DB row, any asset rows, and every
            # object already uploaded to storage.
            if project_id:
                try:
                    cloud.delete_project(project_id, identity.id)
                except Exception:
                    log.exception("rollback of project %s failed", project_id)
            if uploaded_paths:
                try:
                    cloud.remove_objects(uploaded_paths)
                except Exception:
                    log.exception("rollback of %s storage object(s) failed",
                                  len(uploaded_paths))
            project_id = None
            assets_out = [
                asset.to_out(download_url=f"{API_PREFIX}/download/{result.token}/{asset.kind.value}")
                for asset in result.assets
            ]
    if not assets_out:
        assets_out = [
            asset.to_out(download_url=f"{API_PREFIX}/download/{result.token}/{asset.kind.value}")
            for asset in result.assets
        ]

    notes = list(result.notes)
    if cloud_outcome.mode != "cloud":
        _LOCAL_RESULTS[result.token] = (
            time.time(),
            {"workspace": result.workspace, "expires_in": 60 * 60},
        )
    else:
        result.cleanup()

    if not result.assets:
        raise HTTPException(500, "Generation produced no files.")

    log.info("cloud outcome: %s (%s)", cloud_outcome.mode, cloud_outcome.message[:80])

    return GenerateResponse(
        project_id=project_id,
        cloud_saved=cloud_outcome.saved,
        cloud_mode=cloud_outcome.mode,
        cloud_message=cloud_outcome.message,
        theme=ThemeSummary(**result.design.summary()),
        slide_count=result.slide_count,
        assets=assets_out,
        notes=notes,
    )


@app.post(f"{API_PREFIX}/slides/preview", tags=["design"])
def slide_preview(
    brief: GenerateRequest,
    index: int = 0,
    identity: Optional[Identity] = Depends(optional_user),
) -> Response:
    """Render one real slide as a PNG.

    Uses the same outline and design system as the .pptx, so the results studio
    shows the actual generated slide rather than a mock-up. Requires an identity
    whenever Supabase is configured, so previews follow the same access rule as
    the rest of the app.
    """
    cloud = get_cloud()
    if cloud.configured and identity is None:
        raise HTTPException(401, "Sign in to render slide previews.")

    outline = build_outline(brief)
    if not outline:
        raise HTTPException(422, "The brief did not produce any slides.")
    index = max(0, min(index, len(outline) - 1))
    png = cached_slide_png(brief, outline[index], index, len(outline))
    return Response(content=png, media_type="image/png", headers={
        "Cache-Control": "private, max-age=3600",
    })


@app.post(f"{API_PREFIX}/slides/sheet", tags=["design"])
def slide_sheet(
    brief: GenerateRequest,
    identity: Optional[Identity] = Depends(optional_user),
) -> Response:
    """Contact sheet of every slide; used as the project thumbnail."""
    cloud = get_cloud()
    if cloud.configured and identity is None:
        raise HTTPException(401, "Sign in to render slide previews.")
    outline = build_outline(brief)
    design = build_design_system(brief)
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        meta = contact_sheet_png(brief, outline, design, Path(tmp) / "sheet.png")
        data = (Path(tmp) / "sheet.png").read_bytes()
    return Response(content=data, media_type="image/png", headers={
        "X-Sheet-Width": str(meta["width"]),
        "X-Sheet-Height": str(meta["height"]),
        "Cache-Control": "private, max-age=3600",
    })


@app.get(f"{API_PREFIX}/download/{{token}}/{{kind}}", tags=["generation"])
def download_local(
    token: str,
    kind: str,
    identity: Optional[Identity] = Depends(optional_user),
) -> FileResponse:
    """Serve a locally generated file.

    The ``token`` is 128 bits of unguessable randomness and the workspace is
    temporary. When Supabase is configured an authenticated identity is still
    required so a generated link cannot be shared onward.
    """
    cloud = get_cloud()
    if cloud.configured and identity is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Sign in to download from this server. Files are served to authenticated users only.",
        )

    entry = _LOCAL_RESULTS.get(token)
    if not entry:
        raise HTTPException(404, "This development download has expired or was already replaced. "
                                  "Generate the package again.")
    stamp, meta = entry
    if time.time() - stamp > meta["expires_in"]:
        _LOCAL_RESULTS.pop(token, None)
        raise HTTPException(410, "Development download expired. Generate again.")
    workspace: Path = meta["workspace"]
    if not workspace.exists():
        _LOCAL_RESULTS.pop(token, None)
        raise HTTPException(410, "Temporary files were already cleaned up. Generate again.")

    candidates = {
        "presentation": [p for p in workspace.iterdir() if p.suffix.lower() == ".pptx"],
        "poster": [p for p in workspace.iterdir() if p.name.endswith("-poster.png")],
        "social": [p for p in workspace.iterdir() if p.name.endswith("-social.png")],
        "svg": [p for p in workspace.iterdir() if p.suffix.lower() == ".svg"],
    }.get(kind)
    if not candidates:
        raise HTTPException(404, f"Unknown asset kind '{kind}'.")
    target = candidates[0]
    if not target.resolve().is_relative_to(workspace.resolve()):
        raise HTTPException(400, "Invalid file path.")

    media = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
    if kind == "presentation":
        media = ("application/vnd.openxmlformats-officedocument.presentationml.presentation")
    return FileResponse(target, media_type=media, filename=target.name,
                        headers={"Cache-Control": "private, max-age=300"})


@app.get(f"{API_PREFIX}/projects/{{project_id}}/download/{{asset_id}}", tags=["projects"])
def download_cloud(project_id: str, asset_id: str,
                   identity: Identity = Depends(require_user)) -> JSONResponse:
    """Short-lived signed URL for an asset owned by the caller."""
    cloud = get_cloud()
    if not cloud.configured:
        raise HTTPException(503, "Supabase is not configured; signed downloads are unavailable.")
    project = cloud.get_project(project_id, identity.id)
    if not project:
        raise HTTPException(404, "Project not found or not owned by this account.")
    asset = next((a for a in project.get("generated_assets", []) if a.get("id") == asset_id), None)
    if not asset or not asset.get("storage_path"):
        raise HTTPException(404, "Asset not found for this project.")
    url = cloud.signed_url(asset["storage_path"])
    if not url:
        raise HTTPException(502, "Supabase could not issue a signed URL for this asset.")
    return JSONResponse({"download_url": url, "expires_in": cloud.ttl})


# --------------------------------------------------------------------------
# projects
# --------------------------------------------------------------------------
def _to_summary(row: dict) -> ProjectSummary:
    return ProjectSummary(
        id=row["id"],
        project_name=row["project_name"],
        topic=row["topic"],
        style_preset=StylePreset(row["style_preset"]),
        primary_color=row["primary_color"],
        secondary_color=row["secondary_color"],
        brand_name=row.get("brand_name") or row["project_name"],
        tagline=row.get("tagline") or "",
        slide_count=row.get("slide_count") or 0,
        asset_count=len(row.get("generated_assets") or []),
        created_at=row["created_at"],
        updated_at=row.get("updated_at"),
    )


def _asset_out(row: dict, ttl: int) -> dict:
    return {
        "id": row.get("id"),
        "kind": row["kind"],
        "filename": row["filename"],
        "content_type": row["content_type"],
        "size_bytes": row["size_bytes"],
        "width": row.get("width_px"),
        "height": row.get("height_px"),
        "download_url": None,
        "storage_path": row.get("storage_path"),
        "cloud_saved": True,
        "checksum": row.get("checksum"),
    }


@app.get(f"{API_PREFIX}/projects", response_model=list[ProjectSummary], tags=["projects"])
def list_projects(identity: Identity = Depends(require_user)) -> list[ProjectSummary]:
    cloud = get_cloud()
    if not cloud.configured:
        raise HTTPException(503, "Supabase is not configured; there is no project library to read.")
    try:
        rows = cloud.list_projects(identity.id)
    except Exception as exc:
        log.exception("project list failed")
        raise _schema_failure(exc) or HTTPException(
            502, f"Could not load projects: {exc}"
        )
    return [_to_summary(r) for r in rows]


@app.get(f"{API_PREFIX}/projects/{{project_id}}", response_model=ProjectDetail, tags=["projects"])
def get_project(project_id: str, identity: Identity = Depends(require_user)) -> ProjectDetail:
    cloud = get_cloud()
    if not cloud.configured:
        raise HTTPException(503, "Supabase is not configured; project details are unavailable.")
    try:
        row = cloud.get_project(project_id, identity.id)
    except Exception as exc:
        log.exception("project read failed")
        raise _schema_failure(exc) or HTTPException(
            502, f"Could not load project: {exc}"
        )
    if not row:
        raise HTTPException(404, "Project not found or not owned by this account.")
    return ProjectDetail(
        **_to_summary(row).model_dump(),
        goal=row.get("goal") or "",
        audience=row.get("audience") or "",
        tone=row.get("tone") or "",
        presentation_type=PresentationType(row["presentation_type"]),
        visual_style=row.get("visual_style") or "",
        extra_instructions=row.get("extra_instructions") or "",
        brief=row.get("brief_json") or {},
        assets=[_asset_out(a, cloud.ttl) for a in row.get("generated_assets", [])],
    )


@app.delete(f"{API_PREFIX}/projects/{{project_id}}", response_model=DeleteResponse, tags=["projects"])
def delete_project(project_id: str, identity: Identity = Depends(require_user)) -> DeleteResponse:
    cloud = get_cloud()
    if not cloud.configured:
        raise HTTPException(503, "Supabase is not configured; nothing to delete.")
    try:
        deleted, removed = cloud.delete_project(project_id, identity.id)
    except Exception as exc:
        log.exception("project delete failed")
        raise _schema_failure(exc) or HTTPException(
            502, f"Could not delete project: {exc}"
        )
    if not deleted:
        raise HTTPException(404, "Project not found or not owned by this account.")
    return DeleteResponse(
        deleted=True,
        project_id=project_id,
        storage_objects_removed=removed,
        message=f"Deleted project and {removed} storage object(s).",
    )


@app.post(f"{API_PREFIX}/projects/{{project_id}}/regenerate", response_model=GenerateResponse,
          tags=["projects"])
def regenerate(project_id: str, identity: Identity = Depends(require_user)) -> GenerateResponse:
    """Rebuild a saved brief and replace its assets in place."""
    cloud = get_cloud()
    if not cloud.configured:
        raise HTTPException(503, "Supabase is not configured; nothing to regenerate.")
    try:
        row = cloud.get_project(project_id, identity.id)
    except Exception as exc:
        log.exception("project read failed")
        raise _schema_failure(exc) or HTTPException(
            502, f"Could not load project: {exc}"
        )
    if not row:
        raise HTTPException(404, "Project not found or not owned by this account.")
    brief = GenerateRequest(**(row.get("brief_json") or {}))
    result = generate(brief)
    rows = []
    for asset in result.assets:
        data = asset.path.read_bytes()
        path = cloud.upload_asset(project_id, identity.id, asset.filename, data,
                                  asset.content_type)
        rows.append(asset_row(project_id, identity.id, asset.to_out(storage_path=path),
                              path, asset.checksum))
    cloud.replace_assets(project_id, identity.id, rows)
    result.cleanup()
    return GenerateResponse(
        project_id=project_id,
        cloud_saved=True,
        cloud_mode="cloud",
        cloud_message=f"Regenerated and saved to Supabase as project {project_id}.",
        theme=ThemeSummary(**result.design.summary()),
        slide_count=result.slide_count,
        assets=[
            asset.to_out(download_url=cloud.signed_url(r["storage_path"]),
                         storage_path=r["storage_path"], cloud_saved=True, asset_id=r["id"])
            for asset, r in zip(result.assets, rows)
        ],
        notes=result.notes,
    )


@app.head("/api/projects", include_in_schema=False)
def projects_head(x_createflow_probe: Optional[str] = Header(default=None)) -> JSONResponse:
    return JSONResponse(status_code=200, content=None)


# --------------------------------------------------------------------------
# optional static hosting of the built frontend
# --------------------------------------------------------------------------
dist: Path = settings["frontend_dist"]
if dist.is_dir():
    app.mount("/", StaticFiles(directory=str(dist), html=True), name="frontend")
    log.info("serving frontend build from %s", dist)
else:
    @app.get("/", include_in_schema=False)
    def root() -> dict:
        return {
            "name": "CreateFlow API",
            "version": APP_VERSION,
            "docs": "/docs",
            "health": f"{API_PREFIX}/health",
            "note": "Frontend dev server runs on http://localhost:5173",
        }