# AI Automation Project

See [docs/SETUP.md](docs/SETUP.md) for provider credentials, Telegram chat setup, approval behavior, data retention, and Task Scheduler details.

A local Python workflow that researches YouTube topics, creates original Telugu or English stories, generates scene clips, narrates and edits them, and waits for your approval before uploading.

## Workflow

1. Find recent high-velocity videos in a niche with YouTube Data API v3 and retain available view statistics.
2. Generate original plots, scripts, and scene descriptions with Gemini.
3. Render locally animated illustrated village scenes by default; optionally submit and track paid asynchronous Veo jobs.
4. Generate narration locally by default; Azure Speech is optional.
5. Join clips, mix narration, and add subtitles with FFmpeg.
6. Track jobs and approval decisions in SQLite.
7. Review and revise previews by prompt in the Streamlit dashboard and receive Telegram approval notifications.
8. Upload to YouTube only after an explicit approval recorded in Telegram or the dashboard.
9. Run scheduled jobs through Windows Task Scheduler.

## Safety and credentials

- API keys and tokens belong in environment variables or a local `.env` file, never in Git.
- Generated media, local databases, and logs are runtime data and should not be committed.
- Uploading must be gated by a persisted approval decision. Rejection must prevent upload.
- Video-generation providers may complete asynchronously; job state must persist between runs.

## Free-first defaults

The default `VIDEO_PROVIDER=local` renders simple 2D animated village illustrations with FFmpeg instead of calling the
paid Veo API. `SPEECH_PROVIDER=local` uses an installed Windows speech voice and does not call
Azure. Gemini Flash and YouTube Data API use their free quotas when no paid billing project is
linked. Veo and Azure are optional provider choices; check their current quotas/prices before
enabling them. Local animation is drawn by code and is not AI-generated cinematic footage.

## Project modules

The package includes YouTube research, Gemini story writing, local animated village scenes, optional asynchronous Veo generation, local or optional Azure narration, FFmpeg editing, SQLite persistence, Streamlit review, Telegram approvals, and YouTube upload guarded by a persisted approval decision.

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

The dashboard starts empty until you search and create a job. Configure only the API credentials you need in `.env`. Generated media and databases are ignored by Git.

## Provider setup

Add a YouTube Data API key, Gemini API key, Azure Speech resource key and region, and Telegram bot token/chat ID to `.env`. For uploads, download an OAuth **Desktop app** client JSON and put it at `YOUTUBE_OAUTH_CLIENT_SECRETS` (default `secrets/youtube-client-secret.json`). The first approved upload opens Google's local OAuth consent flow; its token is stored under the Git-ignored `secrets/` directory. Start a chat with your Telegram bot before configuring the numeric `TELEGRAM_CHAT_ID`.

Upload visibility is selected for each job in the dashboard and shown in its Telegram message; it defaults to `private` and can be changed with `YOUTUBE_UPLOAD_PRIVACY`. An approved item triggers upload. If OAuth is not ready, approval stays saved and you can retry from the dashboard or with `story-video upload-approved JOB_ID`. A job left in `uploading` has an uncertain remote outcome; check YouTube Studio before retrying to avoid duplicates.

## Asynchronous jobs and scheduling

The channel identity is fixed in code: peaceful Telugu village stories set in the 1980s, with traditional vintage life, calm narration, moral values, and recurring characters in a connected serial. The dashboard has no niche selector; it automatically searches YouTube for the fixed niche, with an optional episode idea to narrow the search. Results from the last 30 days are ranked by estimated views per day, a trend signal rather than an official YouTube trending feed. The top three results are automatically sent to Gemini as trend references to write a new original story; source footage is not downloaded or reused. Each new episode continues the latest approved story and ends with a hook. A pending episode must be approved or rejected before the next episode can be created. You can revise an awaiting-approval draft with a prompt and review the preview. Prompt revisions regenerate the free local 2D animated village scenes. This is procedural illustration, not AI-generated cinematic footage. Veo jobs are asynchronous; run `story-video process-pending` to poll them. Install current-user Windows Task Scheduler tasks with:

```powershell
.\scripts\install-scheduled-tasks.ps1
```

The processor runs every 10 minutes by default; pass `-IntervalMinutes 5` to change it. Set `SCHEDULED_TOPIC` in `.env` to create a new job daily; set `SCHEDULED_LANGUAGE=te` or `en`. The daily generation task defaults to 09:00 local time; pass `-DailyAt "18:30"` to change it. The Telegram approval bot starts at sign-in. Every generated job still waits for a human decision. Remove the tasks with `Unregister-ScheduledTask` for `AI Automation Process Pending Jobs`, `AI Automation Create Scheduled Video`, and `AI Automation Telegram Approval Bot`.

The workflow uses YouTube results as topic research only and does not download or reuse source videos. Cached YouTube metadata and statistics are deleted within 30 days. Upload metadata marks generated video as synthetic media.
