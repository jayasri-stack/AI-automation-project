"""YouTube search and current public statistics collection."""

from __future__ import annotations

from typing import Any

from story_video_automation.config import get_settings
from story_video_automation.options import Options


def search_videos(query: str, language: str, limit: int | None = None) -> list[dict[str, Any]]:
    """Search public YouTube videos, then hydrate the result IDs with current statistics.

    Video IDs and statistics are refreshed each search. Other API metadata is ephemeral and
    should be deleted or refreshed within 30 days under YouTube's developer policies.
    """
    settings = get_settings()
    options = Options.from_env()
    if not settings.youtube_api_key:
        raise RuntimeError("Set YOUTUBE_API_KEY to search YouTube")
    if not query.strip():
        raise ValueError("A non-empty YouTube research query is required")

    try:
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError('Install the "youtube" extra to search YouTube') from exc

    service = build("youtube", "v3", developerKey=settings.youtube_api_key,
                    cache_discovery=False)
    count = limit or options.youtube_result_limit
    search = service.search().list(
        part="snippet",
        q=query.strip(),
        type="video",
        maxResults=max(1, min(50, count)),
        order="relevance",
        safeSearch="moderate",
        regionCode=options.youtube_region,
        relevanceLanguage="te" if language == "te" else "en",
    ).execute()
    ids = [item.get("id", {}).get("videoId") for item in search.get("items", [])]
    ids = [video_id for video_id in ids if video_id]
    if not ids:
        return []

    response = service.videos().list(
        part="snippet,statistics,contentDetails",
        id=",".join(ids),
        maxResults=len(ids),
    ).execute()
    videos_by_id = {item["id"]: item for item in response.get("items", [])}
    ordered: list[dict[str, Any]] = []
    for video_id in ids:
        item = videos_by_id.get(video_id)
        if not item:
            continue
        snippet = item.get("snippet", {})
        stats = item.get("statistics", {})
        ordered.append({
            "video_id": video_id,
            "title": snippet.get("title", "Untitled video"),
            "channel_title": snippet.get("channelTitle", ""),
            "description": snippet.get("description", ""),
            "published_at": snippet.get("publishedAt"),
            "view_count": _optional_int(stats.get("viewCount")),
            "like_count": _optional_int(stats.get("likeCount")),
            "comment_count": _optional_int(stats.get("commentCount")),
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "thumbnail_url": _thumbnail(snippet.get("thumbnails", {})),
            "duration": item.get("contentDetails", {}).get("duration"),
        })
    return ordered


def _optional_int(value: str | int | None) -> int | None:
    return int(value) if value is not None else None


def _thumbnail(thumbnails: dict[str, Any]) -> str | None:
    for size in ("high", "medium", "default"):
        if thumbnails.get(size, {}).get("url"):
            return thumbnails[size]["url"]
    return None
