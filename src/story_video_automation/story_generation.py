"""Original story, narration, and visual scene generation with Gemini."""

from __future__ import annotations

import json
from typing import Any

from story_video_automation.config import get_settings
from story_video_automation.options import Options


def generate_story(
    topic: str,
    language: str,
    scene_count: int | None = None,
    revision_prompt: str | None = None,
    previous_story: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate a structured, original script based on topic-level research signals."""
    settings = get_settings()
    options = Options.from_env()
    if not settings.gemini_api_key:
        raise RuntimeError("Set GEMINI_API_KEY to generate a story")
    if language not in {"te", "en"}:
        raise ValueError("language must be 'te' (Telugu) or 'en' (English)")

    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise RuntimeError('Install the "gemini" extra to use Gemini') from exc

    lang = "Telugu" if language == "te" else "English"
    count = scene_count or options.scene_count
    revision = ""
    if revision_prompt:
        revision = f"""
Revise the previous story using these requested changes: {revision_prompt}
Preserve aspects not mentioned in the request. Previous synopsis: {previous_story.get('synopsis', '') if previous_story else ''}
Previous script: {previous_story.get('script', '') if previous_story else ''}
Previous scene prompts and narration: {json.dumps(previous_story.get('scenes', []), ensure_ascii=False) if previous_story else '[]'}
"""
    prompt = f"""Create a wholly original short-film story in {lang} about: {topic}.
{revision}

Return only valid JSON with this exact shape:
{{"title":"...","synopsis":"...","script":"...","scenes":[
  {{"visual_prompt":"...","narration":"..."}}
]}}

Produce exactly {count} scenes in story order. Keep visual_prompt in English for the video
generator. Write narration and the script in {lang}. Give every scene one coherent visual
action and narration suitable for a short voice-over. Keep characters, setting, wardrobe,
and style consistent across all scene prompts. Avoid references to real people or copyrighted
characters. The full script must be the narration lines joined in order.
"""
    client = genai.Client(api_key=settings.gemini_api_key)
    response = client.models.generate_content(
        model=options.text_model,
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    try:
        data = json.loads(response.text or "")
    except (ValueError, TypeError) as exc:
        raise RuntimeError("Gemini returned invalid story JSON") from exc

    scenes = data.get("scenes")
    if not isinstance(scenes, list) or len(scenes) != count:
        raise RuntimeError(f"Gemini story must contain exactly {count} scenes")
    clean_scenes = []
    for scene in scenes:
        visual = str(scene.get("visual_prompt", "")).strip()
        narration = str(scene.get("narration", "")).strip()
        if not visual or not narration:
            raise RuntimeError("Every scene needs a visual prompt and narration")
        clean_scenes.append({"visual_prompt": visual, "narration": narration})
    title = str(data.get("title", "")).strip()
    synopsis = str(data.get("synopsis", "")).strip()
    script = "\n\n".join(scene["narration"] for scene in clean_scenes)
    if not title or not synopsis:
        raise RuntimeError("Gemini story is missing a title or synopsis")
    return {"title": title, "synopsis": synopsis, "script": script,
            "language": language, "scenes": clean_scenes}
