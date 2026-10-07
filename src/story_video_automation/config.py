"""Environment-based application settings."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional during direct source inspection
    load_dotenv = None


@dataclass(frozen=True, slots=True)
class Settings:
    database_path: Path
    output_dir: Path
    youtube_api_key: str | None
    gemini_api_key: str | None
    azure_speech_key: str | None
    azure_speech_region: str | None
    telegram_bot_token: str | None
    telegram_chat_id: str | None
    youtube_oauth_client_secrets: Path
    ffmpeg_path: str


def get_settings() -> Settings:
    """Load local .env values and return settings without requiring API credentials."""
    if load_dotenv is not None:
        load_dotenv()

    return Settings(
        database_path=Path(os.getenv("DATABASE_PATH", "data/automation.sqlite3")),
        output_dir=Path(os.getenv("OUTPUT_DIR", "generated")),
        youtube_api_key=os.getenv("YOUTUBE_API_KEY") or None,
        gemini_api_key=os.getenv("GEMINI_API_KEY") or None,
        azure_speech_key=os.getenv("AZURE_SPEECH_KEY") or None,
        azure_speech_region=os.getenv("AZURE_SPEECH_REGION") or None,
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN") or None,
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID") or None,
        youtube_oauth_client_secrets=Path(
            os.getenv("YOUTUBE_OAUTH_CLIENT_SECRETS", "secrets/youtube-client-secret.json")
        ),
        ffmpeg_path=os.getenv("FFMPEG_PATH", "ffmpeg"),
    )
