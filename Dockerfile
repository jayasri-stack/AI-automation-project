FROM node:22-bookworm-slim AS frontend-build
WORKDIR /app/frontend
RUN corepack enable && corepack prepare pnpm@11.25.0 --activate
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm run build

FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    API_HOST=0.0.0.0 \
    API_PORT=8000 \
    ENVIRONMENT=production \
    DATABASE_PATH=/data/automation.sqlite3 \
    OUTPUT_DIR=/data/generated
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg espeak-ng libespeak1 ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -e ".[all]"
COPY --from=frontend-build /app/frontend/dist ./frontend/dist
VOLUME ["/data", "/app/secrets"]
EXPOSE 8000
CMD ["story-video-api"]
