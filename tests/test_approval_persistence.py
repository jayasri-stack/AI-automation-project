import pytest

from story_video_automation.db import (
    connect,
    create_job,
    initialize_database,
    mark_uploaded,
    record_approval,
    require_upload_approval,
)


def test_upload_requires_a_persisted_approval_and_preview(tmp_path) -> None:
    database = tmp_path / "approval.sqlite3"
    initialize_database(database)
    job_id = create_job("Episode 1", "te", database)
    with connect(database) as connection:
        connection.execute(
            "UPDATE jobs SET status='awaiting_approval' WHERE id=?", (job_id,)
        )

    record_approval(job_id, "approved", reviewer="test", database_path=database)
    with pytest.raises(ValueError, match="finished video artifact"):
        require_upload_approval(job_id, database_path=database)

    with connect(database) as connection:
        connection.execute(
            "UPDATE jobs SET preview_path=? WHERE id=?", ("preview.mp4", job_id)
        )
    approved = require_upload_approval(job_id, database_path=database)
    assert approved["status"] == "approved"

    with pytest.raises(PermissionError, match="Upload completion requires"):
        mark_uploaded(job_id, "video-123", database_path=database)

    with connect(database) as connection:
        connection.execute("UPDATE jobs SET status='uploading' WHERE id=?", (job_id,))
    mark_uploaded(job_id, "video-123", database_path=database)
    with connect(database) as connection:
        saved = connection.execute("SELECT status, youtube_video_id FROM jobs WHERE id=?", (job_id,)).fetchone()
    assert saved["status"] == "uploaded"
    assert saved["youtube_video_id"] == "video-123"


def test_rejected_job_cannot_be_uploaded(tmp_path) -> None:
    database = tmp_path / "rejected.sqlite3"
    initialize_database(database)
    job_id = create_job("Episode 1", "te", database)
    with connect(database) as connection:
        connection.execute(
            "UPDATE jobs SET status='awaiting_approval', preview_path='preview.mp4' WHERE id=?",
            (job_id,),
        )

    record_approval(job_id, "rejected", reviewer="test", database_path=database)
    with pytest.raises(PermissionError, match="explicit persisted approval"):
        require_upload_approval(job_id, database_path=database)
