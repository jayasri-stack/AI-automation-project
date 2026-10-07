"""Workflow-specific SQLite records and guarded job-state transitions."""

from __future__ import annotations

import shutil
from typing import Any
from pathlib import Path

from story_video_automation.config import get_settings
from story_video_automation.db import connect, create_job, initialize_database

ACTIVE = {
    "queued": {"researching", "failed"},
    "researching": {"writing", "failed"},
    "writing": {"generating_video", "failed"},
    "generating_video": {"narrating", "failed"},
    "narrating": {"editing", "failed"},
    "editing": {"awaiting_approval", "failed"},
    "awaiting_approval": {"approved", "rejected", "failed"},
    "approved": {"uploading", "failed"},
    "uploading": {"uploaded", "failed", "approved"},
    "rejected": set(),
    "uploaded": set(),
    "failed": {"queued"},
}

EXTRA_SCHEMA = """
CREATE TABLE IF NOT EXISTS job_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    from_status TEXT,
    to_status TEXT NOT NULL,
    detail TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_job_events_job ON job_events(job_id, id);

CREATE TABLE IF NOT EXISTS research_videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    video_id TEXT NOT NULL,
    title TEXT NOT NULL,
    channel_title TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    published_at TEXT,
    view_count INTEGER,
    like_count INTEGER,
    comment_count INTEGER,
    url TEXT NOT NULL,
    thumbnail_url TEXT,
    duration TEXT,
    collected_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(job_id, video_id)
);

CREATE TABLE IF NOT EXISTS stories (
    job_id INTEGER PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
    synopsis TEXT NOT NULL,
    script TEXT NOT NULL,
    language TEXT NOT NULL CHECK (language IN ('te', 'en')),
    channel_niche TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS scenes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    scene_number INTEGER NOT NULL,
    visual_prompt TEXT NOT NULL,
    narration TEXT NOT NULL,
    operation_name TEXT,
    operation_state TEXT NOT NULL DEFAULT 'pending',
    video_path TEXT,
    audio_path TEXT,
    subtitle_start_ms INTEGER,
    subtitle_end_ms INTEGER,
    UNIQUE(job_id, scene_number)
);
CREATE INDEX IF NOT EXISTS idx_scenes_job ON scenes(job_id, scene_number);

CREATE TABLE IF NOT EXISTS job_upload_settings (
    job_id INTEGER PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
    privacy_status TEXT NOT NULL CHECK (privacy_status IN ('private', 'unlisted', 'public')),
    made_for_kids INTEGER CHECK (made_for_kids IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS channel_profile (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    niche TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def initialize() -> None:
    """Create the base and workflow tables, safely supporting older local DBs."""
    initialize_database()
    with connect() as connection:
        connection.executescript(EXTRA_SCHEMA)
        columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(research_videos)")
        }
        for name in ("thumbnail_url", "duration"):
            if name not in columns:
                connection.execute(f"ALTER TABLE research_videos ADD COLUMN {name} TEXT")
        upload_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(job_upload_settings)")
        }
        if "made_for_kids" not in upload_columns:
            connection.execute(
                "ALTER TABLE job_upload_settings ADD COLUMN made_for_kids INTEGER"
            )
        story_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(stories)")
        }
        if "channel_niche" not in story_columns:
            connection.execute("ALTER TABLE stories ADD COLUMN channel_niche TEXT NOT NULL DEFAULT ''")
        connection.execute(
            "DELETE FROM research_videos WHERE collected_at < datetime('now', '-30 days')"
        )


def create_workflow_job(title: str, language: str, query: str) -> int:
    if not title.strip() or not query.strip():
        raise ValueError("A title and research query are required")
    initialize()
    job_id = create_job(title.strip(), language)
    with connect() as connection:
        connection.execute(
            "INSERT INTO job_events (job_id, from_status, to_status, detail) VALUES (?, NULL, 'queued', ?)",
            (job_id, f"Research query: {query.strip()}"),
        )
    return job_id


def get_channel_niche() -> str:
    with connect() as connection:
        row = connection.execute("SELECT niche FROM channel_profile WHERE id = 1").fetchone()
    return str(row["niche"]) if row else (
        "Peaceful, calm Telugu village stories set in the 1980s, with traditional daily life, "
        "pleasant narration, and meaningful moral lessons."
    )


def set_channel_niche(niche: str) -> None:
    niche = niche.strip()
    if not niche:
        raise ValueError("Choose or enter a channel niche")
    with connect() as connection:
        connection.execute(
            """INSERT INTO channel_profile(id, niche) VALUES (1, ?)
               ON CONFLICT(id) DO UPDATE SET niche=excluded.niche,
                 updated_at=CURRENT_TIMESTAMP""",
            (niche[:120],),
        )


def transition(job_id: int, target: str, detail: str | None = None) -> None:
    """Change a job status only along the declared workflow graph."""
    with connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute("SELECT status FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            raise LookupError(f"Job {job_id} does not exist")
        source = str(row["status"])
        if target not in ACTIVE.get(source, set()):
            raise ValueError(f"Invalid job transition: {source} -> {target}")
        connection.execute(
            "UPDATE jobs SET status = ?, error = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (target, detail if target == "failed" else None, job_id),
        )
        connection.execute(
            "INSERT INTO job_events (job_id, from_status, to_status, detail) VALUES (?, ?, ?, ?)",
            (job_id, source, target, detail),
        )


def save_research(job_id: int, videos: list[dict[str, Any]]) -> None:
    values = []
    for video in videos:
        values.append({
            "job_id": job_id,
            "video_id": video["video_id"],
            "title": video.get("title", "Untitled video"),
            "channel_title": video.get("channel_title", ""),
            "description": video.get("description", ""),
            "published_at": video.get("published_at"),
            "view_count": video.get("view_count"),
            "like_count": video.get("like_count"),
            "comment_count": video.get("comment_count"),
            "url": video["url"],
            "thumbnail_url": video.get("thumbnail_url"),
            "duration": video.get("duration"),
        })
    with connect() as connection:
        connection.executemany(
            """INSERT INTO research_videos
               (job_id, video_id, title, channel_title, description, published_at,
                view_count, like_count, comment_count, url, thumbnail_url, duration)
               VALUES (:job_id, :video_id, :title, :channel_title, :description,
                       :published_at, :view_count, :like_count, :comment_count, :url,
                       :thumbnail_url, :duration)
               ON CONFLICT(job_id, video_id) DO UPDATE SET
                 title=excluded.title, channel_title=excluded.channel_title,
                 description=excluded.description, published_at=excluded.published_at,
                 view_count=excluded.view_count, like_count=excluded.like_count,
                 comment_count=excluded.comment_count, url=excluded.url,
                 thumbnail_url=excluded.thumbnail_url, duration=excluded.duration,
                 collected_at=CURRENT_TIMESTAMP""",
            values,
        )


def save_story(job_id: int, synopsis: str, script: str, language: str,
               scenes: list[dict[str, str]], channel_niche: str = "") -> None:
    with connect() as connection:
        connection.execute(
            """INSERT INTO stories(job_id, synopsis, script, language, channel_niche)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(job_id) DO UPDATE SET synopsis=excluded.synopsis,
                 script=excluded.script, language=excluded.language,
                 channel_niche=excluded.channel_niche, created_at=CURRENT_TIMESTAMP""",
            (job_id, synopsis, script, language, channel_niche),
        )
        connection.execute("DELETE FROM scenes WHERE job_id = ?", (job_id,))
        connection.executemany(
            "INSERT INTO scenes(job_id, scene_number, visual_prompt, narration) VALUES (?, ?, ?, ?)",
            [(job_id, i + 1, scene["visual_prompt"], scene["narration"]) for i, scene in enumerate(scenes)],
        )


def update_scene(job_id: int, scene_number: int, **values: Any) -> None:
    allowed = {"operation_name", "operation_state", "video_path", "audio_path",
               "subtitle_start_ms", "subtitle_end_ms"}
    updates = {key: value for key, value in values.items() if key in allowed}
    if not updates:
        return
    assignments = ", ".join(f"{key} = ?" for key in updates)
    with connect() as connection:
        cursor = connection.execute(
            f"UPDATE scenes SET {assignments} WHERE job_id = ? AND scene_number = ?",
            (*updates.values(), job_id, scene_number),
        )
        if cursor.rowcount != 1:
            raise LookupError(f"Scene {scene_number} for job {job_id} does not exist")


def get_story(job_id: int) -> dict[str, Any] | None:
    with connect() as connection:
        story = connection.execute("SELECT * FROM stories WHERE job_id = ?", (job_id,)).fetchone()
        scenes = connection.execute(
            "SELECT * FROM scenes WHERE job_id = ? ORDER BY scene_number", (job_id,)
        ).fetchall()
    if story is None:
        return None
    return {**dict(story), "scenes": [dict(row) for row in scenes]}


def list_research(job_id: int) -> list[dict[str, Any]]:
    with connect() as connection:
        rows = connection.execute(
            "SELECT * FROM research_videos WHERE job_id = ? ORDER BY view_count DESC",
            (job_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def list_events(job_id: int) -> list[dict[str, Any]]:
    with connect() as connection:
        rows = connection.execute(
            "SELECT * FROM job_events WHERE job_id = ? ORDER BY id", (job_id,)
        ).fetchall()
    return [dict(row) for row in rows]


def add_job_event(job_id: int, detail: str) -> None:
    """Record a non-state-changing review or revision event."""
    with connect() as connection:
        connection.execute(
            "INSERT INTO job_events(job_id, from_status, to_status, detail) VALUES (?, ?, ?, ?)",
            (job_id, "awaiting_approval", "awaiting_approval", detail[:2000]),
        )


def set_job_title(job_id: int, title: str) -> None:
    with connect() as connection:
        cursor = connection.execute(
            "UPDATE jobs SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (title.strip()[:100], job_id),
        )
        if cursor.rowcount != 1:
            raise LookupError(f"Job {job_id} does not exist")


def set_preview_path(job_id: int, path: str) -> None:
    with connect() as connection:
        cursor = connection.execute(
            "UPDATE jobs SET preview_path = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (path, job_id),
        )
        if cursor.rowcount != 1:
            raise LookupError(f"Job {job_id} does not exist")


def set_upload_settings(
    job_id: int,
    privacy_status: str,
    made_for_kids: bool | None,
) -> None:
    if privacy_status not in {"private", "unlisted", "public"}:
        raise ValueError("privacy_status must be private, unlisted, or public")
    with connect() as connection:
        connection.execute(
            """INSERT INTO job_upload_settings(job_id, privacy_status, made_for_kids)
               VALUES (?, ?, ?)
               ON CONFLICT(job_id) DO UPDATE SET privacy_status=excluded.privacy_status,
                 made_for_kids=excluded.made_for_kids""",
            (job_id, privacy_status, None if made_for_kids is None else int(made_for_kids)),
        )


def get_upload_privacy(job_id: int) -> str:
    from story_video_automation.options import Options

    with connect() as connection:
        row = connection.execute(
            "SELECT privacy_status FROM job_upload_settings WHERE job_id = ?", (job_id,)
        ).fetchone()
    return str(row["privacy_status"]) if row else Options.from_env().upload_privacy


def get_made_for_kids(job_id: int) -> bool | None:
    from story_video_automation.options import Options

    with connect() as connection:
        row = connection.execute(
            "SELECT made_for_kids FROM job_upload_settings WHERE job_id = ?", (job_id,)
        ).fetchone()
    if row is None or row["made_for_kids"] is None:
        return Options.from_env().made_for_kids
    return bool(row["made_for_kids"])


def record_decision_event(job_id: int, decision: str, reviewer: str) -> None:
    with connect() as connection:
        connection.execute(
            "INSERT INTO job_events(job_id, from_status, to_status, detail) VALUES (?, ?, ?, ?)",
            (job_id, "awaiting_approval", decision, f"Decision by {reviewer}"),
        )


def pending_video_jobs() -> list[dict[str, Any]]:
    from story_video_automation.db import list_jobs

    return [job for job in list_jobs() if job["status"] == "generating_video"]


def delete_expired_youtube_data(days: int = 30) -> int:
    """Delete cached YouTube API metadata before its 30-day retention limit."""
    safe_days = max(1, min(30, int(days)))
    with connect() as connection:
        cursor = connection.execute(
            "DELETE FROM research_videos WHERE collected_at < datetime('now', ?)",
            (f"-{safe_days} days",),
        )
        return cursor.rowcount


def delete_job(job_id: int) -> None:
    """Delete a job's database data and generated files under the configured output root."""
    output_root = get_settings().output_dir.resolve()
    artifact_dir = (output_root / f"job_{job_id}").resolve()
    if not artifact_dir.is_relative_to(output_root):
        raise ValueError("Refusing to delete an artifact path outside OUTPUT_DIR")
    with connect() as connection:
        exists = connection.execute("SELECT 1 FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if exists is None:
        raise LookupError(f"Job {job_id} does not exist")
    if artifact_dir.exists():
        shutil.rmtree(artifact_dir)
    with connect() as connection:
        cursor = connection.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        if cursor.rowcount != 1:
            raise RuntimeError("Job disappeared while its local artifacts were being removed")


def reset_uncertain_upload(job_id: int, confirmed_absent: bool) -> None:
    """Allow a manual retry only after the operator confirms YouTube has no uploaded video."""
    if not confirmed_absent:
        raise PermissionError("Confirm in YouTube Studio that the video does not exist")
    with connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute("SELECT status FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            raise LookupError(f"Job {job_id} does not exist")
        if row["status"] != "uploading":
            raise ValueError("Only an uncertain uploading job can be reset")
        connection.execute(
            "UPDATE jobs SET status='approved', updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (job_id,),
        )
        connection.execute(
            """INSERT INTO job_events(job_id, from_status, to_status, detail)
               VALUES (?, 'uploading', 'approved', ?)""",
            (job_id, "Operator confirmed no matching video exists in YouTube Studio"),
        )
