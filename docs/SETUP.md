# Setup and operations

## Provider credentials

Copy `.env.example` to `.env` and set only the credentials for services you use.

- **YouTube research:** Create a Google Cloud project, enable YouTube Data API v3, and set its API key as `YOUTUBE_API_KEY`.
- **Gemini stories and Veo clips:** Create a Gemini API key and set `GEMINI_API_KEY`. Veo access and billing must be enabled for the selected account/project. `GEMINI_VIDEO_MODEL` and `GEMINI_TEXT_MODEL` can be changed without code edits.
- **Azure narration:** Set the Speech resource key and region. Telugu uses `te-IN-ShrutiNeural` by default; set `AZURE_TELUGU_VOICE` to `te-IN-MohanNeural` if you prefer the male voice. English defaults to `en-US-AriaNeural`.
- **Telegram approvals:** Create a bot with BotFather. Set `TELEGRAM_BOT_TOKEN`, send `/start` to the bot, and run `story-video telegram-chat-id`. Copy the printed numeric ID to `TELEGRAM_CHAT_ID`. The bot ignores approval actions from every other chat.
- **YouTube upload:** Create an OAuth client of type **Desktop app** and set its JSON path as `YOUTUBE_OAUTH_CLIENT_SECRETS`. The first approved upload opens an OAuth consent window requesting only the YouTube upload scope. The refresh token is stored at `secrets/youtube-token.json`; never commit it.

FFmpeg and FFprobe must be installed separately. The FFmpeg build needs H.264 (`libx264`), AAC, and subtitle/libass support. Set `FFMPEG_PATH` if `ffmpeg` is not on `PATH`. `BACKGROUND_MUSIC` is optional and must point to audio you have the right to use.

## Workflow and approvals

In Streamlit, enter a topic, search YouTube, select the references to keep with the job, choose Telugu or English, and choose the upload visibility. Search-result titles and statistics are shown as YouTube data and are not sent to Gemini. Gemini creates an original story from the topic you entered.

Veo returns long-running operation names. Those names and scene states are stored in SQLite so `story-video process-pending` can poll again after a restart. Once all clips are ready, the worker creates per-scene narration, mixes scene audio with narration, adds optional background music, burns subtitles into the preview, then sends approval buttons.

Approval in Streamlit or Telegram writes a durable decision before upload begins. A rejection cannot be uploaded. The selected visibility is shown in Streamlit and Telegram; uploads default to private. A job left in `uploading` has an uncertain remote outcome after a network failure. Check YouTube Studio before any retry; the workflow deliberately avoids automatic duplicate uploads. If no video exists, confirm that in the dashboard before resetting the job to approved.

## Scheduling

For daily automatic job creation, set `SCHEDULED_TOPIC` and `SCHEDULED_LANGUAGE` in `.env`, then run `scripts/install-scheduled-tasks.ps1`. It registers:

- A processor that polls asynchronous jobs every 10 minutes by default (`-IntervalMinutes 5` changes that).
- A daily job creator at 09:00 local time (`-DailyAt "18:30"` changes that).
- A Telegram bot process at user sign-in.

Every scheduled job still waits for approval. The desktop session must be running for the Telegram bot and local OAuth consent flow.
Each scheduled generation uses YouTube and Gemini/Veo API quota and may incur provider charges. Leave `SCHEDULED_TOPIC` empty and do not install the scheduled creator if you only want jobs started manually in Streamlit.

## Local data and security

The app runs locally. The SQLite DB and generated outputs stay under `DATABASE_PATH` and `OUTPUT_DIR`, both ignored by Git, along with `.env` and OAuth credentials. Delete a job from the dashboard to remove its database data and generated files. YouTube research metadata/statistics are deleted after at most 30 days. See [PRIVACY.md](PRIVACY.md).

## API references

- [YouTube search](https://developers.google.com/youtube/v3/docs/search/list) and [video statistics](https://developers.google.com/youtube/v3/docs/videos)
- [Gemini Veo video generation and asynchronous operations](https://ai.google.dev/gemini-api/docs/veo)
- [Azure Speech text to speech](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/get-started-text-to-speech)
- [YouTube video upload](https://developers.google.com/youtube/v3/docs/videos/insert)
- [YouTube data refresh and retention policies](https://developers.google.com/youtube/terms/developer-policies)
