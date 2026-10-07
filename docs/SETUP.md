# Setup and operations

## Provider credentials

Copy `.env.example` to `.env`. The defaults use local scene cards and local speech; no Veo or
Azure request is made unless you explicitly change the provider settings.

- **YouTube research:** Create a Google Cloud project, enable YouTube Data API v3, and set its API key as `YOUTUBE_API_KEY`.
- **Gemini stories:** Create a Gemini API key and leave the project on a free-tier model/project; do not link billing if you need to avoid charges. Free-tier limits apply and can change. Gemini free-tier requests may be used to improve Google's products.
- **Veo clips (optional, paid):** Only set `VIDEO_PROVIDER=veo` if you decide to use paid Veo. Its API has no free tier; review pricing before enabling it.
- **Narration:** The default local speech mode uses a voice installed in Windows. If no Telugu voice is installed, add a Telugu voice through Windows language/speech settings before processing Telugu jobs. Optional Azure Speech mode uses `SPEECH_PROVIDER=azure` and requires a Speech key and region; only use it after confirming the resource is on the F0 free tier.
- **Telegram approvals:** Create a bot with BotFather. Set `TELEGRAM_BOT_TOKEN`, send `/start` to the bot, and run `story-video telegram-chat-id`. Copy the printed numeric ID to `TELEGRAM_CHAT_ID`. The bot ignores approval actions from every other chat.
- **YouTube upload:** Create an OAuth client of type **Desktop app** and set its JSON path as `YOUTUBE_OAUTH_CLIENT_SECRETS`. The first approved upload opens an OAuth consent window requesting only the YouTube upload scope. The refresh token is stored at `secrets/youtube-token.json`; never commit it.

FFmpeg and FFprobe must be installed separately. The FFmpeg build needs H.264 (`libx264`), AAC, and subtitle/libass support. Set `FFMPEG_PATH` if `ffmpeg` is not on `PATH`. `BACKGROUND_MUSIC` is optional and must point to audio you have the right to use.

## Workflow and approvals

In Streamlit, describe and save your channel niche and signature style, optionally enter today's episode idea, find recent high-view videos, select references, choose Telugu or English, and choose upload visibility. For example: peaceful Telugu village stories set in the 1980s, traditional life, calm narration, and a gentle moral. Future stories use the saved profile for a consistent channel identity. Results cover the last 30 days and are ranked by estimated views per day; this is a useful niche trend signal, not an official YouTube trending feed. YouTube Data API has a default daily quota; API quota is not a cash balance. The titles, descriptions, and public statistics of videos you select are sent to Gemini to identify broad audience trends and write a new original story. The source videos themselves are not downloaded or reused.

In free-first local mode, FFmpeg creates stylized scene cards without a video-generation API. These are assembled into a video preview but are not AI-generated motion footage. You can request prompt-based script/scene-card revisions while the draft awaits approval; each revision creates a new preview, sends a fresh Telegram notification, and invalidates old Telegram buttons. If you opt into Veo, its long-running operation names are stored in SQLite so `story-video process-pending` can poll after a restart. Once scenes are ready, the worker creates per-scene narration, mixes scene audio with narration, adds optional background music, burns subtitles into the preview, then sends approval buttons.

Approval in Streamlit or Telegram writes a durable decision before upload begins. A rejection cannot be uploaded. The selected visibility is shown in Streamlit and Telegram; uploads default to private. A job left in `uploading` has an uncertain remote outcome after a network failure. Check YouTube Studio before any retry; the workflow deliberately avoids automatic duplicate uploads. If no video exists, confirm that in the dashboard before resetting the job to approved.

## Scheduling

For daily automatic job creation, set `SCHEDULED_TOPIC` and `SCHEDULED_LANGUAGE` in `.env`, then run `scripts/install-scheduled-tasks.ps1`. It registers:

- A processor that polls asynchronous jobs every 10 minutes by default (`-IntervalMinutes 5` changes that).
- A daily job creator at 09:00 local time (`-DailyAt "18:30"` changes that).
- A Telegram bot process at user sign-in.

Every scheduled job still waits for approval. The desktop session must be running for the Telegram bot and local OAuth consent flow.
Each scheduled generation uses YouTube and Gemini API quota. Local scene cards incur no provider charge. Veo or Azure may incur charges if explicitly enabled. Leave `SCHEDULED_TOPIC` empty and do not install the scheduled creator if you only want jobs started manually in Streamlit.

## Local data and security

The app runs locally. The SQLite DB and generated outputs stay under `DATABASE_PATH` and `OUTPUT_DIR`, both ignored by Git, along with `.env` and OAuth credentials. Delete a job from the dashboard to remove its database data and generated files. YouTube research metadata/statistics are deleted after at most 30 days. See [PRIVACY.md](PRIVACY.md).

## API references

- [YouTube search](https://developers.google.com/youtube/v3/docs/search/list) and [video statistics](https://developers.google.com/youtube/v3/docs/videos)
- [Gemini Veo video generation and asynchronous operations](https://ai.google.dev/gemini-api/docs/veo)
- [Azure Speech text to speech](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/get-started-text-to-speech)
- [YouTube video upload](https://developers.google.com/youtube/v3/docs/videos/insert)
- [YouTube data refresh and retention policies](https://developers.google.com/youtube/terms/developer-policies)
