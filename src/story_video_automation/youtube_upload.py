"""Approval-gated YouTube upload using the user's OAuth-authorized channel."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from story_video_automation.config import get_settings
from story_video_automation.options import Options

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def authorized_service() -> Any:
    settings = get_settings()
    client_file = settings.youtube_oauth_client_secrets
    token_file = Path("secrets/youtube-token.json")
    if not client_file.is_file():
        raise RuntimeError(
            "Add your OAuth desktop client JSON at YOUTUBE_OAUTH_CLIENT_SECRETS before upload"
        )
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError('Install the "youtube" extra to upload') from exc

    credentials = None
    if token_file.is_file():
        credentials = Credentials.from_authorized_user_file(str(token_file), SCOPES)
    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
    if not credentials or not credentials.valid:
        flow = InstalledAppFlow.from_client_secrets_file(str(client_file), SCOPES)
        credentials = flow.run_local_server(port=0, access_type="offline", prompt="consent")
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(credentials.to_json(), encoding="utf-8")
    return build("youtube", "v3", credentials=credentials, cache_discovery=False)


def upload_video(
    video_path: Path,
    title: str,
    description: str,
    language: str,
    service: Any | None = None,
    privacy_status: str | None = None,
    made_for_kids: bool | None = None,
) -> str:
    """Upload one finished video; callers must establish persisted approval first."""
    if not video_path.is_file() or video_path.stat().st_size == 0:
        raise FileNotFoundError(f"Finished video is missing: {video_path}")
    try:
        from googleapiclient.http import MediaFileUpload
    except ImportError as exc:
        raise RuntimeError('Install the "youtube" extra to upload') from exc

    service = service or authorized_service()
    options = Options.from_env()
    privacy = privacy_status or options.upload_privacy
    if privacy not in {"private", "unlisted", "public"}:
        raise ValueError("privacy_status must be private, unlisted, or public")
    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "categoryId": "24",
            "defaultLanguage": "te" if language == "te" else "en",
        },
        "status": {"privacyStatus": privacy, "containsSyntheticMedia": True},
    }
    if made_for_kids is not None:
        body["status"]["selfDeclaredMadeForKids"] = made_for_kids
    request = service.videos().insert(
        part="snippet,status",
        body=body,
        media_body=MediaFileUpload(
            str(video_path), mimetype="video/mp4", chunksize=8 * 1024 * 1024, resumable=True
        ),
    )
    response = None
    while response is None:
        _, response = request.next_chunk()
    video_id = response.get("id")
    if not video_id:
        raise RuntimeError("YouTube completed the upload without returning a video ID")
    return str(video_id)
