"""Non-secret tuning options for provider integrations."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name)
    value = default if raw is None else int(raw)
    return min(maximum, max(minimum, value))


@dataclass(frozen=True, slots=True)
class Options:
    youtube_region: str = "IN"
    youtube_result_limit: int = 8
    text_model: str = "gemini-2.5-flash"
    video_model: str = "veo-3.1-generate-preview"
    video_aspect_ratio: str = "9:16"
    scene_count: int = 5
    telugu_voice: str = "te-IN-ShrutiNeural"
    upload_privacy: str = "private"
    telegram_poll_seconds: int = 5
    api_data_retention_days: int = 30
    scheduled_topic: str | None = None
    scheduled_language: str = "te"
    made_for_kids: bool | None = None

    @classmethod
    def from_env(cls) -> "Options":
        privacy = os.getenv("YOUTUBE_UPLOAD_PRIVACY", "private").lower()
        if privacy not in {"private", "unlisted", "public"}:
            raise ValueError("YOUTUBE_UPLOAD_PRIVACY must be private, unlisted, or public")
        ratio = os.getenv("VIDEO_ASPECT_RATIO", "9:16")
        if ratio not in {"9:16", "16:9"}:
            raise ValueError("VIDEO_ASPECT_RATIO must be 9:16 or 16:9")
        scheduled_language = os.getenv("SCHEDULED_LANGUAGE", "te").lower()
        if scheduled_language not in {"te", "en"}:
            raise ValueError("SCHEDULED_LANGUAGE must be te or en")
        raw_kids = os.getenv("YOUTUBE_MADE_FOR_KIDS", "").strip().lower()
        if raw_kids in {"true", "yes", "1"}:
            made_for_kids: bool | None = True
        elif raw_kids in {"false", "no", "0"}:
            made_for_kids = False
        elif raw_kids == "":
            made_for_kids = None
        else:
            raise ValueError("YOUTUBE_MADE_FOR_KIDS must be true, false, or empty")
        return cls(
            youtube_region=os.getenv("YOUTUBE_REGION", "IN").upper(),
            youtube_result_limit=_int("YOUTUBE_RESULT_LIMIT", 8, 1, 50),
            text_model=os.getenv("GEMINI_TEXT_MODEL", "gemini-2.5-flash"),
            video_model=os.getenv("GEMINI_VIDEO_MODEL", "veo-3.1-generate-preview"),
            video_aspect_ratio=ratio,
            scene_count=_int("STORY_SCENE_COUNT", 5, 2, 12),
            telugu_voice=os.getenv("AZURE_TELUGU_VOICE", "te-IN-ShrutiNeural"),
            upload_privacy=privacy,
            telegram_poll_seconds=_int("TELEGRAM_POLL_SECONDS", 5, 1, 30),
            api_data_retention_days=min(30, _int("YOUTUBE_API_DATA_RETENTION_DAYS", 30, 1, 30)),
            scheduled_topic=os.getenv("SCHEDULED_TOPIC") or None,
            scheduled_language=scheduled_language,
            made_for_kids=made_for_kids,
        )
