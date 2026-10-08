from __future__ import annotations

import pytest

from story_video_automation.db import connect
from story_video_automation.state import create_workflow_job, initialize


def test_only_one_serial_episode_can_be_active(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "serial.sqlite3"))
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "generated"))
    initialize()

    first_id = create_workflow_job("Episode idea one", "te", "village stories")

    with pytest.raises(ValueError, match="still processing"):
        create_workflow_job("Episode idea two", "te", "village stories")

    with connect() as connection:
        connection.execute("UPDATE jobs SET status='failed' WHERE id=?", (first_id,))

    second_id = create_workflow_job("Episode idea two", "te", "village stories")
    assert second_id > first_id


def test_waiting_for_review_blocks_the_next_episode(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "serial.sqlite3"))
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "generated"))
    initialize()
    first_id = create_workflow_job("Episode idea one", "te", "village stories")
    with connect() as connection:
        connection.execute(
            "UPDATE jobs SET status='awaiting_approval' WHERE id=?", (first_id,)
        )

    with pytest.raises(ValueError, match="awaiting review"):
        create_workflow_job("Episode idea two", "te", "village stories")
