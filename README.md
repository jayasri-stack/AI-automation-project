# AI Automation Project

A Python workflow for researching story ideas, generating original Telugu or English scripts and scene descriptions, producing video and narration, assembling reviewable previews, and publishing only after explicit approval.

## Workflow

1. Research relevant YouTube videos with YouTube Data API v3 and retain available view statistics.
2. Generate original plots, scripts, and scene descriptions with Gemini.
3. Submit and track asynchronous scene-video generation jobs.
4. Generate Telugu narration with Azure Speech.
5. Join clips, mix narration, and add subtitles with FFmpeg.
6. Track jobs and approval decisions in SQLite.
7. Review previews in the Streamlit dashboard and receive Telegram approval notifications.
8. Upload to YouTube only after an explicit approval recorded in Telegram or the dashboard.
9. Run scheduled jobs through Windows Task Scheduler.

## Safety and credentials

- API keys and tokens belong in environment variables or a local `.env` file, never in Git.
- Generated media, local databases, and logs are runtime data and should not be committed.
- Uploading must be gated by a persisted approval decision. Rejection must prevent upload.
- Video-generation providers may complete asynchronously; job state must persist between runs.

## First milestone

The initial foundation provides environment-based configuration, a SQLite job and approval store, a Streamlit review screen, and an approval check for upload workflows. Provider integrations and scheduling will be added in later milestones.

## Setup

Requires Python 3.11 or newer. Install the base app with:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[all]"
Copy-Item .env.example .env
```

Install FFmpeg separately and ensure it is on `PATH` (or set `FFMPEG_PATH`). Add credentials to `.env` only for integrations you enable.

Initialize the local database:

```powershell
story-video init-db
```

Run the dashboard:

```powershell
streamlit run src/story_video_automation/dashboard.py
```

The dashboard starts empty until workflow jobs are created. No provider calls or video uploads are enabled by this foundation milestone.
