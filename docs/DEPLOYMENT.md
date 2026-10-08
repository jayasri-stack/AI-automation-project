# Local and container deployment

## Local Windows demo

Follow the README setup steps, then start `story-video-api`. The production React files are served from the same FastAPI origin at `http://127.0.0.1:8000`; `/docs` exposes the OpenAPI page. For frontend hot reload, run Vite separately at `http://127.0.0.1:5173`.

The app needs YouTube Data API and Gemini credentials to research and write episodes. Telegram, Azure Speech, and YouTube OAuth are optional integrations. Never commit `.env`, OAuth files, generated media, SQLite databases, or logs.

## Docker Compose

1. Install Docker Desktop.
2. Copy `.env.example` to `.env`.
3. Add the provider credentials you plan to use and set `API_AUTH_TOKEN` to a long random secret. `ENVIRONMENT=production` refuses to start without this token.
4. Run `docker compose up --build` and browse to `http://localhost:8000`.

Compose stores SQLite and generated files in the named `story-data` volume and mounts local `secrets/` for the optional YouTube OAuth client and token. Back up those locations before replacing the container. Docker binds the port to the local machine; for remote access, configure TLS, authentication, and a reverse proxy before changing that binding.

## Operational limits

- The local workflow is intended for one user and one machine. SQLite is not configured for multi-worker web deployments.
- Local scene rendering and the current API's generation request are synchronous and can take time. For a multi-user production service, move generation into a durable queue/worker before scaling out.
- Upload decisions are recorded before upload. If the job is left in `uploading`, check YouTube Studio before retrying because the remote result may be uncertain.
- A container does not include a Telugu system voice by default. Use Azure Speech with its configured region/key or run on a host with an installed Telugu voice.
- YouTube and Gemini free quotas can change and are controlled by their providers. Veo, Azure, hosting, and bandwidth may incur charges.
