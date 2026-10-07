# Local data and privacy

This project runs on the computer where you start Streamlit, the Telegram bot, and the scheduled worker. It is not a hosted service.

## Data sent to providers

- YouTube Data API receives the search query and returns video IDs, titles, channel names, descriptions, publication times, and current public statistics.
- Gemini receives your saved channel niche, the topic you enter, and metadata for the YouTube videos you select (titles, channel names, descriptions, publication dates, and public statistics). It uses selected-video metadata to infer broad audience interests and create an original script and scene prompts; the project does not download or reuse source footage. YouTube descriptions are external content and are treated only as research text.
- Azure Speech receives each scene's narration text to create audio.
- Telegram receives the job title, job number, selected upload visibility, and inline approve/reject buttons.
- YouTube receives the final MP4 and upload metadata only after you approve the job in the dashboard or the configured Telegram chat.

## Local storage and deletion

Credentials are read from `.env`, the local OAuth client JSON, and the OAuth refresh token under `secrets/`. The database is stored at `DATABASE_PATH`; generated scripts, clips, audio, and previews are stored under `OUTPUT_DIR`. Those locations are ignored by Git.

The dashboard can delete a job and its generated artifacts. This also deletes its cached YouTube API metadata. Cached YouTube metadata and statistics are otherwise deleted within 30 days. To remove upload credentials, delete `.env`, the OAuth client JSON, and `secrets/youtube-token.json`; revoke the app's access in your Google Account security settings if needed.

This local privacy notice describes this project's behavior. If you distribute the app or use it for other people, publish an appropriate privacy policy and update the Google OAuth consent configuration before sharing it.
