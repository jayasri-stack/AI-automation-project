"""Human approval decisions and immediate upload dispatch."""

from __future__ import annotations

from pathlib import Path

from story_video_automation.db import connect, record_approval, require_upload_approval
from story_video_automation.state import (
    get_story,
    get_made_for_kids,
    get_upload_privacy,
    record_decision_event,
    transition,
)
from story_video_automation.youtube_upload import authorized_service, upload_video


def decide(job_id: int, decision: str, reviewer: str) -> str | None:
    """Persist a dashboard/Telegram decision; approved items upload immediately.

    OAuth setup happens before the job enters `uploading`, so configuration failures leave
    the approved job retryable. A job in `uploading` is never retried automatically because a
    lost network response can leave the remote outcome uncertain.
    """
    record_approval(job_id, decision, reviewer=reviewer)
    record_decision_event(job_id, decision, reviewer)
    if decision != "approved":
        return None
    if get_made_for_kids(job_id) is None:
        raise ValueError("Choose whether this video is made for kids in the dashboard before upload")
    return upload_approved_job(job_id)


def upload_approved_job(job_id: int) -> str:
    """Upload a video only after re-reading its persisted approved state."""
    job = require_upload_approval(job_id)
    story = get_story(job_id)
    if story is None:
        raise RuntimeError("Approved job has no saved story metadata")
    made_for_kids = get_made_for_kids(job_id)
    if made_for_kids is None:
        raise ValueError("Choose whether this video is made for kids before upload")

    # Finish local credential setup before marking the remote operation uncertain.
    service = authorized_service()
    transition(job_id, "uploading", "Upload started after persisted human approval")
    try:
        video_id = upload_video(
            video_path=Path(job["preview_path"]),
            title=str(job["title"]),
            description=story["synopsis"],
            language=story["language"],
            service=service,
            privacy_status=get_upload_privacy(job_id),
            made_for_kids=made_for_kids,
        )
    except Exception:
        # Keep `uploading` as an explicit uncertain state to prevent accidental duplicates.
        raise

    with connect() as connection:
        connection.execute(
            """UPDATE jobs SET status='uploaded', youtube_video_id=?, updated_at=CURRENT_TIMESTAMP
               WHERE id=? AND status='uploading'""",
            (video_id, job_id),
        )
        updated = connection.execute("SELECT changes()").fetchone()[0]
        if updated != 1:
            raise RuntimeError("Upload succeeded but the job record could not be finalized")
        connection.execute(
            "INSERT INTO job_events(job_id, from_status, to_status, detail) VALUES (?, ?, ?, ?)",
            (job_id, "uploading", "uploaded", f"YouTube video ID: {video_id}"),
        )
    return video_id
