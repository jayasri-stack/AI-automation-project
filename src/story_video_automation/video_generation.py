"""Asynchronous scene generation with Gemini's Veo video API."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from story_video_automation.config import get_settings
from story_video_automation.options import Options


def _client() -> Any:
    settings = get_settings()
    if not settings.gemini_api_key:
        raise RuntimeError("Set GEMINI_API_KEY to generate video scenes")
    try:
        from google import genai
    except ImportError as exc:
        raise RuntimeError('Install the "gemini" extra to use Veo') from exc
    return genai.Client(api_key=settings.gemini_api_key)


def submit_scene(prompt: str) -> str:
    """Submit one long-running scene operation and return its durable operation name."""
    options = Options.from_env()
    from google.genai import types

    operation = _client().models.generate_videos(
        model=options.video_model,
        prompt=prompt,
        config=types.GenerateVideosConfig(aspect_ratio=options.video_aspect_ratio),
    )
    name = getattr(operation, "name", None)
    if not name:
        raise RuntimeError("Gemini video generation returned no operation name")
    return str(name)


def poll_scene(operation_name: str, destination: Path) -> dict[str, Any]:
    """Poll a single Veo operation without blocking; download the clip only when done."""
    from google.genai import types

    client = _client()
    operation = client.operations.get(types.GenerateVideosOperation(name=operation_name))
    if not getattr(operation, "done", False):
        return {"state": "pending"}
    error = getattr(operation, "error", None)
    if error:
        message = getattr(error, "message", None) or str(error)
        return {"state": "failed", "error": message}

    response = getattr(operation, "response", None)
    generated = getattr(response, "generated_videos", None) or []
    if not generated:
        return {"state": "failed", "error": "Completed operation contained no video"}
    destination.parent.mkdir(parents=True, exist_ok=True)
    client.files.download(file=generated[0].video, destination=str(destination))
    if not destination.is_file() or destination.stat().st_size == 0:
        return {"state": "failed", "error": "Video download was empty"}
    return {"state": "done", "path": str(destination)}
