from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from story_video_automation import api
from story_video_automation.db import connect, create_job


@pytest.fixture
def client(tmp_path, monkeypatch) -> Iterator[TestClient]:
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "api.sqlite3"))
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "generated"))
    monkeypatch.delenv("API_AUTH_TOKEN", raising=False)
    with TestClient(api.app) as test_client:
        yield test_client


def test_health_and_fixed_channel_config(client: TestClient) -> None:
    assert client.get("/api/health").json()["status"] == "ok"
    assert "1980s" in client.get("/api/config").json()["niche"]


def test_jobs_list_and_missing_job(client: TestClient) -> None:
    job_id = create_job("Village episode", "te")

    response = client.get("/api/jobs")
    missing = client.get("/api/jobs/99999")

    assert response.status_code == 200
    assert response.json()[0]["id"] == job_id
    assert response.json()[0]["story"] is None
    assert missing.status_code == 404


def test_research_always_includes_the_fixed_niche(client: TestClient, monkeypatch) -> None:
    observed: dict[str, str] = {}

    def fake_search(query: str, language: str):
        observed.update(query=query, language=language)
        return [{"title": "Village story", "video_id": "abc"}]

    monkeypatch.setattr(api, "search_videos", fake_search)
    response = client.post("/api/research", json={"topic": "lost calf", "language": "te"})

    assert response.status_code == 200
    assert "1980s" in observed["query"]
    assert "lost calf" in observed["query"]
    assert observed["language"] == "te"


def test_review_route_persists_rejection_without_upload(client: TestClient) -> None:
    job_id = create_job("Village episode", "te")
    with connect() as connection:
        connection.execute("UPDATE jobs SET status='awaiting_approval' WHERE id=?", (job_id,))

    response = client.post(f"/api/jobs/{job_id}/decision", json={"decision": "rejected"})

    assert response.status_code == 200
    assert response.json()["job"]["status"] == "rejected"
    assert "no upload" in response.json()["message"].lower()


def test_api_token_is_required_when_configured(client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("API_AUTH_TOKEN", "local-test-token")

    denied = client.get("/api/jobs")
    allowed = client.get("/api/jobs", headers={"Authorization": "Bearer local-test-token"})

    assert denied.status_code == 401
    assert allowed.status_code == 200
