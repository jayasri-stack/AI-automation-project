"""Command-line entry points for local project setup."""

from __future__ import annotations

import argparse

from story_video_automation.db import initialize_database


def main() -> None:
    parser = argparse.ArgumentParser(prog="story-video")
    parser.add_argument(
        "command",
        choices=["init-db"],
        help="Initialize the local SQLite database",
    )
    args = parser.parse_args()

    if args.command == "init-db":
        initialize_database()
        print("Database initialized.")


if __name__ == "__main__":
    main()
