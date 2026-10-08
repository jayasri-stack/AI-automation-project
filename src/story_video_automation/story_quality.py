"""Deterministic quality checks for trend-informed serialized story drafts."""

from __future__ import annotations

import re
from typing import Any


def _normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def evaluate_story(
    story: dict[str, Any],
    trend_references: list[dict[str, Any]] | None = None,
    *,
    expected_scene_count: int | None = None,
    language: str | None = None,
    previous_episode: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate story structure, serial fields, narration consistency, and title originality."""
    errors: list[str] = []
    warnings: list[str] = []
    checks: dict[str, bool] = {}

    title = str(story.get("title", "")).strip()
    synopsis = str(story.get("synopsis", "")).strip()
    checks["title_present"] = bool(title)
    checks["synopsis_present"] = bool(synopsis)
    if not title:
        errors.append("A title is required.")
    if not synopsis:
        errors.append("A synopsis is required.")
    checks["title_length"] = len(title) <= 100
    if title and len(title) > 100:
        errors.append("The title must be 100 characters or fewer.")

    scenes = story.get("scenes")
    valid_scenes = isinstance(scenes, list) and bool(scenes)
    if not valid_scenes:
        errors.append("At least one scene is required.")
        scenes = []
    narrations: list[str] = []
    valid_scene_fields = True
    for number, scene in enumerate(scenes, start=1):
        if not isinstance(scene, dict):
            errors.append(f"Scene {number} must be an object.")
            valid_scene_fields = False
            continue
        visual = str(scene.get("visual_prompt", "")).strip()
        narration = str(scene.get("narration", "")).strip()
        if not visual or not narration:
            errors.append(f"Scene {number} needs a visual prompt and narration.")
            valid_scene_fields = False
        narrations.append(narration)
    checks["scene_fields"] = valid_scene_fields and valid_scenes
    checks["scene_count"] = expected_scene_count is None or len(scenes) == expected_scene_count
    if not checks["scene_count"]:
        errors.append(f"Expected {expected_scene_count} scenes; received {len(scenes)}.")

    script = str(story.get("script", "")).strip()
    checks["script_matches_scenes"] = bool(script) and script == "\n\n".join(narrations)
    if not checks["script_matches_scenes"]:
        errors.append("The script must exactly match the ordered scene narration.")

    references = trend_references or []
    insights = story.get("trend_insights")
    insights_valid = isinstance(insights, dict)
    if references:
        insights_valid = insights_valid and bool(insights.get("themes")) and bool(insights.get("audience_hooks"))
    checks["trend_insights"] = bool(insights_valid)
    if not insights_valid:
        errors.append("Trend references require themes and audience hooks in trend_insights.")

    bible = story.get("series_bible")
    bible_valid = (
        isinstance(bible, dict)
        and bool(str(bible.get("setting", "")).strip())
        and isinstance(bible.get("characters"), list)
        and bool(bible["characters"])
        and isinstance(bible.get("unresolved_threads"), list)
    )
    checks["series_bible"] = bool(bible_valid)
    if not bible_valid:
        errors.append("A series bible needs a setting, characters, and unresolved_threads.")
    if previous_episode:
        old_bible = previous_episode.get("series_bible", {})
        old_characters = old_bible.get("characters", []) if isinstance(old_bible, dict) else []
        current_characters = bible.get("characters", []) if isinstance(bible, dict) else []

        def character_name(character: Any) -> str:
            if isinstance(character, dict):
                return str(character.get("name", "")).strip().casefold()
            return str(character).strip().casefold()

        previous_names = {character_name(item) for item in old_characters if character_name(item)}
        current_names = {character_name(item) for item in current_characters if character_name(item)}
        missing_names = previous_names - current_names
        checks["recurring_characters_preserved"] = not missing_names
        if missing_names:
            errors.append("The series bible dropped recurring characters: " + ", ".join(sorted(missing_names)))
    checks["continuity_bridge"] = bool(str(story.get("continuity_bridge", "")).strip())
    if not checks["continuity_bridge"]:
        errors.append("A continuity bridge is required.")
    checks["next_episode_hook"] = bool(str(story.get("next_episode_hook", "")).strip())
    if not checks["next_episode_hook"]:
        errors.append("A hook for the next episode is required.")

    normalized_title = _normalized(title)
    copied_title = any(
        normalized_title and normalized_title == _normalized(str(ref.get("title", "")))
        for ref in references
    )
    checks["title_originality"] = not copied_title
    if copied_title:
        errors.append("The generated title exactly matches a trend reference title.")
    selected_language = language or story.get("language")
    if selected_language == "te" and not any("\u0c00" <= char <= "\u0c7f" for char in script):
        warnings.append("Telugu was selected, but the narration contains no Telugu characters.")

    return {"passed": not errors, "checks": checks, "errors": errors, "warnings": warnings}
