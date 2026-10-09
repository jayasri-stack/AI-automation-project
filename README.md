# AI Automation Project

See [docs/SETUP.md](docs/SETUP.md) for provider credentials, Telegram chat setup, approval behavior, data retention, and Task Scheduler details.

A local Python workflow that researches YouTube topics, creates original Telugu or English stories, generates scene clips, narrates and edits them, and waits for your approval before uploading.

## Workflow

1. Search several Telugu village and vintage themes with YouTube Data API v3, then rank matching videos by estimated views per day.
2. Generate original plots, scripts, and scene descriptions locally with Ollama by default; Gemini is optional.
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

The default `TEXT_PROVIDER=ollama` runs the Qwen3 story model on your PC without a story API key.
`VIDEO_PROVIDER=local` renders simple 2D animated village illustrations with FFmpeg, and
`SPEECH_PROVIDER=local` uses an installed Windows speech voice. YouTube research still uses its
API quota. Gemini is optional; Veo and Azure may incur charges if enabled. Local animation is
drawn by code and is not AI-generated cinematic footage.

## Story quality and continuous checks

Every generated draft is checked before rendering: scene narration must match the script, required serial fields must be present, trend insights must be recorded when references are used, and a generated title cannot exactly copy a researched title. The dashboard shows trend summaries, the series bible, the next-episode hook, and the check result. These deterministic checks catch structural problems; they do not replace a human review of story quality.

Install development tools and run the same checks used by GitHub Actions:

```powershell
pip install -e ".[dev]"
ruff check src tests
pytest -q
```

## Project modules

The package includes YouTube research, local Ollama story writing (with optional Gemini), local animated village scenes, optional asynchronous Veo generation, local or optional Azure narration, FFmpeg editing, SQLite persistence, Streamlit review, Telegram approvals, and YouTube upload guarded by a persisted approval decision.

## Browser dashboard and API

The React dashboard is the main browser interface. It searches several village and vintage themes in Telugu or English, matching the episode language, creates an episode draft, previews the rendered video, shows continuity and draft checks, accepts revision prompts, and records approve/reject decisions. The FastAPI service exposes the same workflow and interactive API documentation at `/docs`. Streamlit remains available as an alternate local dashboard.

### Run on Windows

Install Python 3.11+, FFmpeg, and Node.js 22+ (Node's installer includes npm). In the repository folder:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[all]"
Copy-Item .env.example .env
npm install --global pnpm@11.25.0
pnpm --dir frontend install
pnpm --dir frontend build
```

Add a YouTube Data API key to `.env` for research. Story writing uses local Ollama by default; install Ollama and pull the configured model before creating a story. Gemini, Telegram, and upload OAuth are optional. Local Telugu narration needs a Telugu voice installed in Windows, or the optional Azure Speech provider. Start the app with `story-video-api`, then open **http://127.0.0.1:8000** in Chrome. The API docs are at **http://127.0.0.1:8000/docs**. To develop the UI with hot reload, run `story-video-api` in one terminal and `pnpm --dir frontend dev` in another, then open **http://127.0.0.1:5173**.

The API listens only on `127.0.0.1` by default. If `API_AUTH_TOKEN` is set, enter the same token in the dashboard's API connection panel. Do not expose this local development server directly to the public internet.

### Run with Docker

Docker builds both the React bundle and Python API. Copy `.env.example` to `.env`, add the provider keys you need, and set a long random `API_AUTH_TOKEN`. Then run:

```powershell
docker compose up --build
```

Open **http://localhost:8000** and enter the API token in the dashboard. The compose file binds to localhost, persists database/media under a Docker volume, and mounts `secrets/` for YouTube OAuth. For a public deployment, put the service behind HTTPS and an access-controlled reverse proxy; do not publish a token-bearing API directly. Telugu local speech may not be installed in a Linux image; configure Azure Speech or use a host with a Telugu voice.

Folder responsibilities are documented in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), and Docker/local deployment settings are in [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

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

Add a YouTube Data API key to `.env`. Gemini, Azure Speech, and Telegram credentials are optional. For uploads, download an OAuth **Desktop app** client JSON and put it at `YOUTUBE_OAUTH_CLIENT_SECRETS` (default `secrets/youtube-client-secret.json`). The first approved upload opens Google's local OAuth consent flow; its token is stored under the Git-ignored `secrets/` directory. Start a chat with your Telegram bot before configuring the numeric `TELEGRAM_CHAT_ID`.

Upload visibility is selected for each job in the dashboard and shown in its Telegram message; it defaults to `private` and can be changed with `YOUTUBE_UPLOAD_PRIVACY`. An approved item triggers upload. If OAuth is not ready, approval stays saved and you can retry from the dashboard or with `story-video upload-approved JOB_ID`. A job left in `uploading` has an uncertain remote outcome; check YouTube Studio before retrying to avoid duplicates.

## Asynchronous jobs and scheduling

The channel identity is fixed in code: peaceful Telugu village stories set in the 1980s, with traditional vintage life, calm narration, moral values, and recurring characters in a connected serial. The dashboard has no niche selector; it searches several village life, VHS, cooking, customs, and moral-story themes using Telugu or English queries to match the episode language, with an optional episode idea added as another search. Each theme search consumes YouTube API quota. Videos from any publication date may appear and are ranked by estimated views per day; this is a research signal, not an official YouTube trending feed. The top three results guide an original story; source footage is not downloaded or reused. Each new episode continues the latest approved story and ends with a hook. A pending episode must be approved or rejected before the next episode can be created. You can revise an awaiting-approval draft with a prompt and review the preview. Prompt revisions regenerate the free local 2D animated village scenes. This is procedural illustration, not AI-generated cinematic footage. Veo jobs are asynchronous; run `story-video process-pending` to poll them. Install current-user Windows Task Scheduler tasks with:

```powershell
.\scripts\install-scheduled-tasks.ps1
```

The processor runs every 10 minutes by default; pass `-IntervalMinutes 5` to change it. Set `SCHEDULED_TOPIC` in `.env` to create a new job daily; set `SCHEDULED_LANGUAGE=te` or `en`. The daily generation task defaults to 09:00 local time; pass `-DailyAt "18:30"` to change it. The Telegram approval bot starts at sign-in. Every generated job still waits for a human decision. Remove the tasks with `Unregister-ScheduledTask` for `AI Automation Process Pending Jobs`, `AI Automation Create Scheduled Video`, and `AI Automation Telegram Approval Bot`.

The workflow uses YouTube results as topic research only and does not download or reuse source videos. Cached YouTube metadata and statistics are deleted within 30 days. Upload metadata marks generated video as synthetic media.
