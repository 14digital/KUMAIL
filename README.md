# My Intelligence

A private, source-aware intelligence desk. This repository contains a working **foundation MVP**, not the complete production system in the master specification. See [implementation status](docs/STATUS.md) for the exact boundary.

## Windows: start with Docker Desktop

1. Start Docker Desktop and wait for its engine to run. If it asks for a WSL update, run `wsl --update` in PowerShell and restart Windows.
2. On this GitHub page, select **Code → Download ZIP**, then extract the ZIP in Windows File Explorer.
3. Open the extracted folder and double-click **Start My Intelligence.cmd**.
4. Keep the command window open while the images build. The launcher opens the dashboard and your local `.env` in Notepad.
5. Copy the value after `APP_TOKEN=` into the dashboard access-key field. Keep that file private.

The launcher creates a fresh random access key on your computer. No paid API key is needed to open the app. Provider features require separate configuration. The Windows launcher has not been executed on a Windows machine during this build; the Docker images and private-network routing were tested on Linux.

## Run locally

Prerequisites: Python 3.12+, uv, Node.js 22+ and npm.

```sh
UV_CACHE_DIR=/tmp/my-intelligence-uv uv sync --frozen
cd web && npm ci && npm run build
cd ..
cp .env.example .env
# Set APP_TOKEN to a cryptographically random secret of at least 32 characters.
# Optionally configure OpenAI and ElevenLabs credentials in .env.
./scripts/dev.sh
```

Open the dashboard on port 3000, enter your configured `APP_TOKEN`, and add an approved HTTPS RSS source under Sources. The token is held only in browser memory. No publisher is silently pre-approved. Prepare an edition or wait for a scheduled run. The API is on port 8000; its OpenAPI contracts are available at `/docs` and `/openapi.json` (the schema contains no credentials).

Without API credentials, the application publishes clearly labelled feed excerpts and retrieves relevant authorised document excerpts. It does **not** pretend these are AI summaries or generated audio. With OpenAI configured, synthesis uses the Responses API. With ElevenLabs configured, narration runs asynchronously and authenticated audio is available from the persistent player.

A local `.env` with a random key may already have been created by the build session. Keep it private; do not commit it. All persistent state lives in ignored `state/` by default.

## Containers

```sh
docker compose up --build -d
# Managed Codex environment, preserving proxy and TLS trust:
docker compose -f compose.yaml -f compose.cloud.yaml up --build -d
```

Use HTTPS termination and restrict access before exposing the application outside the host. Compose binds public-facing ports to loopback. Never publish the development server directly to the Internet.

## Tests

```sh
.venv/bin/pytest -q
# With scripts/dev.sh running:
.venv/bin/python scripts/smoke.py
cd web && npm run build
```

API example (token comes from your environment):

```sh
curl -H "Authorization: Bearer $APP_TOKEN" http://localhost:8000/api/dashboard
```

Document ingestion: authenticated `POST /api/documents` accepts `title`, `text` and `permission_confirmed: true`. Delete and export endpoints are available. `POST /api/questions` accepts `question`, `mode` and an optional `conversation_id`. Poll `/api/answers/{id}`. Research and news use different durable queues and processes.

See [architecture](docs/ARCHITECTURE.md), [integration feasibility](docs/FEASIBILITY.md), [security and recovery](docs/OPERATIONS.md) and [status](docs/STATUS.md).
