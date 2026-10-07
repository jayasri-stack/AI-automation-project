"""Command-line entry points for the story video workflow."""

from __future__ import annotations

import argparse
import json

from story_video_automation.db import initialize_database


def main() -> None:
    parser = argparse.ArgumentParser(prog="story-video")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init-db", help="Initialize the SQLite database")
    start = commands.add_parser("start", help="Research a topic and start a new video job")
    start.add_argument("--topic", required=True)
    start.add_argument("--language", choices=["te", "en"], default="te")
    start.add_argument("--made-for-kids", choices=["yes", "no"])
    commands.add_parser("process-pending", help="Poll async video jobs and finish ready previews")
    commands.add_parser("telegram-bot", help="Run the Telegram approval bot")
    commands.add_parser("telegram-chat-id", help="Read pending messages to discover your chat ID")
    commands.add_parser("scheduled-run", help="Start a job from SCHEDULED_TOPIC")
    upload = commands.add_parser("upload-approved", help="Upload one explicitly approved job")
    upload.add_argument("job_id", type=int)
    reset = commands.add_parser(
        "reset-uncertain-upload",
        help="Reset an uncertain upload after confirming it is absent in YouTube Studio",
    )
    reset.add_argument("job_id", type=int)
    reset.add_argument("--confirmed-absent", action="store_true", required=True)
    args = parser.parse_args()

    if args.command == "init-db":
        initialize_database()
        from story_video_automation.state import initialize

        initialize()
        print("Database initialized.")
    elif args.command == "start":
        from story_video_automation.pipeline import start_workflow

        audience = None if args.made_for_kids is None else args.made_for_kids == "yes"
        job_id = start_workflow(args.topic, args.language, made_for_kids=audience)
        print(f"Job {job_id} submitted. Run `story-video process-pending` until its preview is ready.")
    elif args.command == "process-pending":
        from story_video_automation.pipeline import process_pending

        print(json.dumps(process_pending(), indent=2))
    elif args.command == "telegram-bot":
        from story_video_automation.telegram_bot import run_bot

        run_bot()
    elif args.command == "telegram-chat-id":
        from story_video_automation.telegram_bot import print_chat_ids

        print_chat_ids()
    elif args.command == "scheduled-run":
        from story_video_automation.options import Options
        from story_video_automation.pipeline import start_workflow

        options = Options.from_env()
        if not options.scheduled_topic:
            parser.error("Set SCHEDULED_TOPIC in .env before running scheduled-run")
        if options.made_for_kids is None:
            parser.error("Set YOUTUBE_MADE_FOR_KIDS=true or false before running scheduled-run")
        job_id = start_workflow(
            options.scheduled_topic,
            options.scheduled_language,
            made_for_kids=options.made_for_kids,
        )
        print(f"Scheduled job {job_id} submitted.")
    elif args.command == "upload-approved":
        from story_video_automation.approval import upload_approved_job

        video_id = upload_approved_job(args.job_id)
        print(f"Uploaded YouTube video: https://www.youtube.com/watch?v={video_id}")
    elif args.command == "reset-uncertain-upload":
        from story_video_automation.state import reset_uncertain_upload

        reset_uncertain_upload(args.job_id, args.confirmed_absent)
        print("Job reset to approved. You may retry the upload.")


if __name__ == "__main__":
    main()
