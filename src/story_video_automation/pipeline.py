"""End-to-end story video workflow with durable asynchronous Veo jobs."""

from __future__ import annotations

import logging
import os
from uuid import uuid4
from pathlib import Path
from typing import Any

from story_video_automation.azure_speech import synthesize_narration
from story_video_automation.config import get_settings
from story_video_automation.channel_profile import CHANNEL_NICHE, CHANNEL_SEARCH_QUERY
from story_video_automation.media import render_video
from story_video_automation.options import Options
from story_video_automation.state import (
    create_workflow_job,
    add_job_event,
    get_story,
    pending_video_jobs,
    save_research,
    save_story,
    set_job_title,
    set_preview_path,
    set_upload_settings,
    list_research,
    transition,
    update_scene,
)
from story_video_automation.story_generation import generate_story
from story_video_automation.telegram_bot import send_approval_notification
from story_video_automation.video_generation import poll_scene, submit_local_scene, submit_scene
from story_video_automation.youtube_research import search_videos
from story_video_automation.db import list_jobs

logger = logging.getLogger(__name__)


def start_workflow(
    topic: str,
    language: str,
    references: list[dict[str, Any]] | None = None,
    upload_privacy: str | None = None,
    made_for_kids: bool | None = None,
) -> int:
    """Create a job from selected research using local scenes by default."""
    topic = topic.strip()
    if not topic:
        raise ValueError("Enter a story topic or research query")
    sources = (
        references if references is not None
        else search_videos(f"{CHANNEL_SEARCH_QUERY} {topic}", language)
    )
    if not sources:
        raise RuntimeError("No YouTube references were selected or returned")
    _ensure_previous_episode_reviewed()

    job_id = create_workflow_job(topic[:100], language, topic)
    try:
        privacy = upload_privacy or Options.from_env().upload_privacy
        audience_setting = (
            Options.from_env().made_for_kids if made_for_kids is None else made_for_kids
        )
        set_upload_settings(job_id, privacy, audience_setting)
        transition(job_id, "researching", "Collecting current YouTube search metadata")
        save_research(job_id, sources)
        transition(job_id, "writing", "Generating an original story and scene prompts")
        episode_number, previous_episode = _previous_serial_context()
        story = generate_story(
            topic, language, trend_references=sources,
            episode_number=episode_number, previous_episode=previous_episode,
        )
        set_job_title(job_id, f"Episode {episode_number}: {story['title']}")
        save_story(
            job_id, story["synopsis"], story["script"], language, story["scenes"],
            CHANNEL_NICHE, episode_number,
        )

        video_provider = Options.from_env().video_provider
        detail = (
            "Rendering free local animated village scenes"
            if video_provider == "local"
            else "Submitting asynchronous Veo scene generation jobs (paid provider)"
        )
        transition(job_id, "generating_video", detail)
        root = get_settings().output_dir / f"job_{job_id}" / "scenes"
        for scene_number, scene in enumerate(story["scenes"], start=1):
            prompt = (
                f"Original cinematic short-film scene. {scene['visual_prompt']} "
                "Consistent characters and art direction. No captions, logos, or watermarks."
            )
            destination = root / f"scene_{scene_number:02}.mp4"
            if video_provider == "local":
                operation_name = submit_local_scene(prompt, destination)
                operation_state = "done"
            else:
                operation_name = submit_scene(prompt)
                operation_state = "submitted"
            update_scene(
                job_id,
                scene_number,
                operation_name=operation_name,
                operation_state=operation_state,
                video_path=str(destination),
            )
    except Exception as exc:
        _fail_if_active(job_id, exc)
        raise
    return job_id


def process_pending(job_ids: set[int] | None = None) -> dict[str, int]:
    """Poll saved Veo operations once, then narrate/edit completed jobs."""
    from story_video_automation.state import delete_expired_youtube_data, initialize

    initialize()
    deleted = delete_expired_youtube_data(Options.from_env().api_data_retention_days)
    counts = {"pending": 0, "completed": 0, "failed": 0, "expired_records_deleted": deleted}
    pending = pending_video_jobs()
    if job_ids is not None:
        pending = [job for job in pending if int(job["id"]) in job_ids]
    for job in pending:
        job_id = int(job["id"])
        story = get_story(job_id)
        if story is None:
            _fail_if_active(job_id, RuntimeError("Story record is missing"))
            counts["failed"] += 1
            continue
        try:
            still_pending = False
            any_failed = False
            for scene in story["scenes"]:
                if scene["operation_state"] == "done":
                    continue
                if not scene.get("operation_name"):
                    raise RuntimeError(f"Scene {scene['scene_number']} has no saved Veo operation")
                result = poll_scene(
                    scene["operation_name"],
                    Path(scene["video_path"] or "generated/missing.mp4"),
                )
                if result["state"] == "pending":
                    still_pending = True
                elif result["state"] == "failed":
                    update_scene(job_id, scene["scene_number"], operation_state="failed")
                    raise RuntimeError(
                        f"Scene {scene['scene_number']} video generation failed: {result['error']}"
                    )
                else:
                    update_scene(
                        job_id,
                        scene["scene_number"],
                        operation_state="done",
                        video_path=result["path"],
                    )
            if still_pending:
                counts["pending"] += 1
                continue

            transition(job_id, "narrating", "All scene videos completed")
            narrated_scenes: list[dict[str, Any]] = []
            for scene in story["scenes"]:
                audio_path = Path(scene["video_path"]).with_suffix(".wav")
                synthesize_narration(
                    scene["narration"],
                    audio_path,
                    language=story["language"],
                )
                update_scene(job_id, scene["scene_number"], audio_path=str(audio_path))
                narrated_scenes.append({**scene, "audio_path": str(audio_path)})

            transition(job_id, "editing", "Narration generated; assembling scene clips and subtitles")
            settings = get_settings()
            output_dir = settings.output_dir / f"job_{job_id}"
            preview = output_dir / "preview.mp4"
            rendered_scenes = [
                {**scene, "video_path": scene["video_path"], "audio_path": scene["audio_path"]}
                for scene in narrated_scenes
            ]
            music_setting = os.getenv("BACKGROUND_MUSIC", "").strip()
            music_path = Path(music_setting) if music_setting else None
            if music_path and not music_path.is_file():
                raise FileNotFoundError(f"BACKGROUND_MUSIC file not found: {music_path}")
            render_video(rendered_scenes, output_dir, preview, background_music=music_path)
            set_preview_path(job_id, str(preview.resolve()))
            transition(job_id, "awaiting_approval", "Preview is ready for human review")
            counts["completed"] += 1
            try:
                send_approval_notification(job_id)
            except Exception:
                logger.exception("Could not send Telegram approval notification for job %s", job_id)
        except Exception as exc:
            _fail_if_active(job_id, exc)
            counts["failed"] += 1
            logger.exception("Workflow processing failed for job %s", job_id)
    return counts


def revise_preview(job_id: int, instructions: str) -> str:
    """Apply a prompt revision to a local-mode draft and replace its review preview."""
    from story_video_automation.db import list_jobs

    instructions = instructions.strip()
    if not instructions:
        raise ValueError("Describe the changes you want first")
    job = next((item for item in list_jobs() if item["id"] == job_id), None)
    if not job or job["status"] != "awaiting_approval":
        raise ValueError("Only a video awaiting approval can be revised")
    if Options.from_env().video_provider != "local":
        raise ValueError("Prompt revisions are currently available only in free local mode")
    current = get_story(job_id)
    if current is None:
        raise RuntimeError("This job has no saved story to revise")

    revised = generate_story(
        job["title"], current["language"], revision_prompt=instructions,
        previous_story=current,
        trend_references=list_research(job_id),
        episode_number=int(current.get("episode_number", 1)),
        previous_episode=_previous_serial_context(exclude_job_id=job_id)[1],
    )
    from story_video_automation.local_media import render_local_animated_scene

    settings = get_settings()
    revision_dir = settings.output_dir / f"job_{job_id}" / f"revision_{uuid4().hex[:10]}"
    revision_dir.mkdir(parents=True, exist_ok=True)
    rendered: list[dict[str, Any]] = []
    for number, scene in enumerate(revised["scenes"], 1):
        scene_path = revision_dir / f"scene_{number:02}.mp4"
        prompt = (f"Original cinematic short-film scene. {scene['visual_prompt']} "
                  "Consistent characters and art direction. No captions, logos, or watermarks.")
        render_local_animated_scene(prompt, scene_path)
        audio_path = scene_path.with_suffix(".wav")
        synthesize_narration(scene["narration"], audio_path, language=current["language"])
        rendered.append({**scene, "video_path": str(scene_path), "audio_path": str(audio_path)})

    preview = revision_dir / "preview.mp4"
    music_setting = os.getenv("BACKGROUND_MUSIC", "").strip()
    music_path = Path(music_setting) if music_setting else None
    if music_path and not music_path.is_file():
        raise FileNotFoundError(f"BACKGROUND_MUSIC file not found: {music_path}")
    render_video(rendered, revision_dir, preview, background_music=music_path)

    # Persist the new story only after all media renders successfully; approval remains pending.
    save_story(
        job_id, revised["synopsis"], revised["script"], current["language"],
        revised["scenes"], CHANNEL_NICHE, int(current.get("episode_number", 1)),
    )
    for number, scene in enumerate(rendered, 1):
        update_scene(job_id, number, operation_name="local:completed", operation_state="done",
                     video_path=scene["video_path"], audio_path=scene["audio_path"])
    set_job_title(job_id, revised["title"])
    set_preview_path(job_id, str(preview.resolve()))
    add_job_event(job_id, f"Draft revised using prompt: {instructions}")
    try:
        send_approval_notification(job_id)
    except Exception:
        logger.exception("Could not send revised Telegram approval notification for job %s", job_id)
    return str(preview.resolve())


def _previous_serial_context(
    exclude_job_id: int | None = None,
) -> tuple[int, dict[str, Any] | None]:
    """Return the next episode number and latest approved/current story in this serial."""
    eligible = {"approved", "uploading", "uploaded"}
    episodes: list[tuple[int, dict[str, Any]]] = []
    for job in list_jobs():
        if int(job["id"]) == exclude_job_id or job["status"] not in eligible:
            continue
        story = get_story(int(job["id"]))
        if not story or story.get("channel_niche") != CHANNEL_NICHE:
            continue
        number = int(story.get("episode_number", 1))
        episodes.append((number, {**story, "title": job["title"]}))
    if not episodes:
        return 1, None
    number, previous = max(episodes, key=lambda item: item[0])
    return number + 1, previous


def _ensure_previous_episode_reviewed() -> None:
    """Require a decision before creating the next installment in the serial."""
    for job in list_jobs():
        if job["status"] != "awaiting_approval":
            continue
        story = get_story(int(job["id"]))
        if story and story.get("channel_niche") == CHANNEL_NICHE:
            raise ValueError(
                f"Episode {story.get('episode_number', 1)} is still awaiting review. "
                "Approve or reject it before creating the next episode."
            )


def _fail_if_active(job_id: int, error: Exception) -> None:
    from story_video_automation.db import list_jobs

    job = next((item for item in list_jobs() if item["id"] == job_id), None)
    if job and job["status"] not in {"failed", "rejected", "uploaded"}:
        try:
            transition(job_id, "failed", f"{type(error).__name__}: {error}"[:2000])
        except ValueError:
            logger.exception("Could not mark job %s failed", job_id)
