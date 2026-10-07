"""SQLite persistence for workflow jobs and human approval decisions."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from story_video_automation.config import get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    language TEXT NOT NULL CHECK (language IN ('te', 'en')),
    status TEXT NOT NULL CHECK (status IN (
        'queued', 'researching', 'writing', 'generating_video', 'narrating',
        'editing', 'awaiting_approval', 'approved', 'rejected', 'uploading',
        'uploaded', 'failed'
    )),
    preview_path TEXT,
    youtube_video_id TEXT,
    error TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS approval_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    decision TEXT NOT NULL CHECK (decision IN ('approved', 'rejected')),
    reviewer TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_jobs_status_updated
    ON jobs(status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_approval_events_job
    ON approval_events(job_id, created_at DESC);
"""


def connect(database_path: Path | str | None = None) -> sqlite3.Connection:
    """Open a SQLite connection with foreign-key checks enabled."""
    path = Path(database_path) if database_path is not None else get_settings().database_path
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(database_path: Path | str | None = None) -> None:
    """Create the schema if it does not already exist."""
    with connect(database_path) as connection:
        connection.executescript(SCHEMA)


def create_job(
    title: str,
    language: str,
    database_path: Path | str | None = None,
) -> int:
    """Create a queued story/video job and return its ID."""
    if language not in {"te", "en"}:
        raise ValueError("language must be 'te' (Telugu) or 'en' (English)")
    with connect(database_path) as connection:
        cursor = connection.execute(
            "INSERT INTO jobs (title, language, status) VALUES (?, ?, 'queued')",
            (title.strip(), language),
        )
        return int(cursor.lastrowid)


def list_jobs(database_path: Path | str | None = None) -> list[dict[str, Any]]:
    """Return jobs newest first for the review dashboard."""
    with connect(database_path) as connection:
        rows = connection.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC, id DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def record_approval(
    job_id: int,
    decision: str,
    reviewer: str = "dashboard",
    database_path: Path | str | None = None,
) -> None:
    """Record an approval/rejection only for a finished preview awaiting review."""
    if decision not in {"approved", "rejected"}:
        raise ValueError("decision must be 'approved' or 'rejected'")

    with connect(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT status FROM jobs WHERE id = ?", (job_id,)
        ).fetchone()
        if row is None:
            raise LookupError(f"Job {job_id} does not exist")
        if row["status"] != "awaiting_approval":
            raise ValueError("Only jobs awaiting approval can be approved or rejected")

        connection.execute(
            "UPDATE jobs SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (decision, job_id),
        )
        connection.execute(
            "INSERT INTO approval_events (job_id, decision, reviewer) VALUES (?, ?, ?)",
            (job_id, decision, reviewer),
        )


def require_upload_approval(
    job_id: int,
    database_path: Path | str | None = None,
) -> dict[str, Any]:
    """Return an approved job or raise before any upload operation can begin."""
    with connect(database_path) as connection:
        row = connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if row is None:
        raise LookupError(f"Job {job_id} does not exist")
    if row["status"] != "approved":
        raise PermissionError("YouTube upload requires an explicit persisted approval")
    if not row["preview_path"]:
        raise ValueError("Cannot upload a job without a finished video artifact")
    return dict(row)


def mark_uploaded(
    job_id: int,
    youtube_video_id: str,
    database_path: Path | str | None = None,
) -> None:
    """Persist upload completion, rechecking approval at the state transition."""
    with connect(database_path) as connection:
        cursor = connection.execute(
            """UPDATE jobs
               SET status = 'uploaded', youtube_video_id = ?, updated_at = CURRENT_TIMESTAMP
               WHERE id = ? AND status = 'approved' AND preview_path IS NOT NULL""",
            (youtube_video_id, job_id),
        )
        if cursor.rowcount != 1:
            raise PermissionError("Upload completion requires an approved job with a preview")
