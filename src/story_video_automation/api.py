"""Local REST API for the story-video workflow and browser dashboard."""

from __future__ import annotations

import hmac
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from story_video_automation.approval import decide, upload_approved_job
from story_video_automation.channel_profile import CHANNEL_NICHE, CHANNEL_SEARCH_QUERY
from story_video_automation.config import get_settings
from story_video_automation.db import list_jobs
from story_video_automation.options import Options
from story_video_automation.pipeline import process_pending, revise_preview, start_workflow
from story_video_automation.state import (
    get_made_for_kids,
    get_story,
    get_upload_privacy,
    initialize,
    list_events,
    list_research,
)
from story_video_automation.youtube_research import search_videos

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize()
    if os.getenv("ENVIRONMENT", "development").lower() == "production" and not os.getenv("API_AUTH_TOKEN"):
        raise RuntimeError("API_AUTH_TOKEN is required when ENVIRONMENT=production")
    yield


def require_api_access(authorization: str | None = Header(default=None)) -> None:
    expected = os.getenv("API_AUTH_TOKEN", "").strip()
    if not expected:
        return
    supplied = authorization.removeprefix("Bearer ").strip() if authorization else ""
    if not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="A valid bearer token is required")


class ResearchRequest(BaseModel):
    topic: str = Field(default="", max_length=200)
    language: Literal["te", "en"] = "te"


class CreateJobRequest(BaseModel):
    topic: str = Field(min_length=2, max_length=200)
    language: Literal["te", "en"] = "te"
    references: list[dict[str, Any]] = Field(default_factory=list, max_length=8)
    upload_privacy: Literal["private", "unlisted", "public"] = "private"
    made_for_kids: bool | None = None


class DecisionRequest(BaseModel):
    decision: Literal["approved", "rejected"]


class RevisionRequest(BaseModel):
    instructions: str = Field(min_length=3, max_length=2000)


router = APIRouter(prefix="/api", dependencies=[Depends(require_api_access)])


def _job_or_404(job_id: int) -> dict[str, Any]:
    job = next((item for item in list_jobs() if int(item["id"]) == job_id), None)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def _job_detail(job: dict[str, Any]) -> dict[str, Any]:
    job_id = int(job["id"])
    return {
        **job,
        "story": get_story(job_id),
        "research": list_research(job_id),
        "events": list_events(job_id),
        "upload_privacy": get_upload_privacy(job_id),
        "made_for_kids": get_made_for_kids(job_id),
    }


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "story-video-automation"}


@router.get("/config")
def channel_config() -> dict[str, str]:
    return {"niche": CHANNEL_NICHE, "search_query": CHANNEL_SEARCH_QUERY}


@router.get("/jobs")
def jobs() -> list[dict[str, Any]]:
    return [_job_detail(job) for job in list_jobs()]


@router.get("/jobs/{job_id}")
def job_detail(job_id: int) -> dict[str, Any]:
    return _job_detail(_job_or_404(job_id))


@router.get("/jobs/{job_id}/preview")
def preview(job_id: int) -> FileResponse:
    job = _job_or_404(job_id)
    configured_output = get_settings().output_dir.resolve()
    preview_path = Path(job.get("preview_path") or "").resolve()
    if not preview_path.is_relative_to(configured_output):
        raise HTTPException(status_code=404, detail="Preview not found")
    if not preview_path.is_file():
        raise HTTPException(status_code=404, detail="Preview file is missing")
    return FileResponse(preview_path, media_type="video/mp4", filename=f"job-{job_id}.mp4")


@router.post("/research")
def research(request: ResearchRequest) -> list[dict[str, Any]]:
    query = f"{CHANNEL_SEARCH_QUERY} {request.topic.strip()}".strip()
    try:
        return search_videos(query, request.language)
    except Exception as exc:
        logger.exception("YouTube research failed")
        raise HTTPException(status_code=502, detail="YouTube research failed; check API configuration") from exc


@router.post("/jobs", status_code=201)
def create_job(request: CreateJobRequest) -> dict[str, Any]:
    try:
        job_id = start_workflow(
            request.topic,
            request.language,
            references=request.references or None,
            upload_privacy=request.upload_privacy,
            made_for_kids=request.made_for_kids,
        )
        if Options.from_env().video_provider == "local":
            process_pending(job_ids={job_id})
        return _job_detail(_job_or_404(job_id))
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Could not create story video job")
        raise HTTPException(status_code=502, detail="Workflow failed; see the job error in the dashboard") from exc


@router.post("/jobs/{job_id}/decision")
def review_job(job_id: int, request: DecisionRequest) -> dict[str, Any]:
    _job_or_404(job_id)
    try:
        video_id = decide(job_id, request.decision, reviewer="web-dashboard")
        message = "Rejected; no upload was started." if request.decision == "rejected" else (
            f"Approved and uploaded as {video_id}." if video_id else "Approved; upload is ready to retry."
        )
    except Exception as exc:
        logger.exception("Review decision could not complete the upload for job %s", job_id)
        current = _job_or_404(job_id)
        if current["status"] == "uploading":
            message = "Approval was recorded, but the upload result is uncertain. Check YouTube Studio before retrying."
        elif current["status"] == "approved":
            message = f"Approval was saved, but upload could not start: {exc}"
        else:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"message": message, "job": _job_detail(_job_or_404(job_id))}


@router.post("/jobs/{job_id}/retry-upload")
def retry_upload(job_id: int) -> dict[str, Any]:
    _job_or_404(job_id)
    try:
        video_id = upload_approved_job(job_id)
    except Exception as exc:
        logger.exception("Upload retry failed for job %s", job_id)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"message": f"Uploaded as {video_id}.", "job": _job_detail(_job_or_404(job_id))}


@router.post("/jobs/{job_id}/revision")
def revise_job(job_id: int, request: RevisionRequest) -> dict[str, Any]:
    _job_or_404(job_id)
    try:
        preview_path = revise_preview(job_id, request.instructions)
    except (ValueError, RuntimeError, FileNotFoundError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"preview_path": preview_path, "job": _job_detail(_job_or_404(job_id))}


app = FastAPI(
    title="Story Video Automation API",
    version="0.2.0",
    description="Trend-informed, human-approved production workflow for serialized Telugu village stories.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv("FRONTEND_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if origin.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(router)

frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if frontend_dist.is_dir():
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")


def run() -> None:
    """Start the local API and the built browser dashboard, if present."""
    import uvicorn

    uvicorn.run(
        "story_video_automation.api:app",
        host=os.getenv("API_HOST", "127.0.0.1"),
        port=int(os.getenv("API_PORT", "8000")),
        reload=os.getenv("API_RELOAD", "false").lower() == "true",
    )
