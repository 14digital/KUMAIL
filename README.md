# My Intelligence

A private, source-aware intelligence desk. This repository contains a working **foundation MVP**, not the complete production system in the master specification. See [implementation status](docs/STATUS.md) for the exact boundary.

## Windows: start with Docker Desktop

1. Start Docker Desktop and wait for its engine to run. If it asks for a WSL update, run `wsl --update` in PowerShell and restart Windows.
2. On this GitHub page, select **Code → Download ZIP**, then extract the ZIP in Windows File Explorer.
3. Open the extracted folder and double-click **Start My Intelligence.cmd**.
4. Keep the command window open while the images build. The launcher opens the dashboard and your local `.env` in Notepad.
5. Copy the value after `APP_TOKEN=` into the dashboard access-key field. Keep that file private.

The launcher creates a fresh random access key on your computer. No paid API key is needed to open the app. Provider features require separate configuration. The Windows launcher has not been executed on a Windows machine during this build; the Docker images and private-network routing were tested on Linux.

## Windows: update without downloading ZIPs again

Download **[Update My Intelligence.cmd](https://github.com/14digital/KUMAIL/raw/refs/heads/main/Update%20My%20Intelligence.cmd)** once and save it **in your existing app folder**, beside Start My Intelligence.cmd. Double-click it for this and future updates. Git may install once and GitHub may ask for browser sign-in. The updater migrates an unchanged ZIP installation to Git, preserves `.env` and the existing data volume, stops on local code edits and builds only affected application images. It is self-contained; no second file download is needed.

See [Windows updates](docs/WINDOWS_UPDATES.md) for migration safeguards, retry behaviour and testing limits. Updating saved keys only requires restarting the containers, not downloading code.

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

## Import publisher feeds on Windows

With the app already running, double-click **Import Publishers.cmd** in the same project folder. This uses `config/publisher-feeds.json` and the running API container; the importer itself does not require an image rebuild. It tests the exact supplied URLs using normal TLS verification and adds parsable, non-empty feeds with approved publisher links. Four checks run concurrently with bounded retrieval timeouts. Login pages, redirects, inaccessible endpoints and empty/unusable feeds remain unimported. Existing sources are preserved. Re-running is safe: the registry keys sources by the exact feed URL.

A local `publisher-import-results.json` records per-feed results and check times. It is ignored by Git. A feed passing this check does not establish full-article permissions, date eligibility or three-source corroboration. Sources outside the 33-feed file have not been added. No paywall bypass or alternate source substitution is performed.

After import, refresh **Sources**, then click **Prepare briefing**. Audio still requires ElevenLabs credentials. The news date parser supports both RSS dates and ISO/Atom dates; rebuild the app after updating backend code to use the latter fix.

## Containers

```sh
docker compose build api web
docker compose up -d --no-build
# Managed Codex environment, preserving proxy and TLS trust:
docker compose -f compose.yaml -f compose.cloud.yaml build api web
docker compose -f compose.yaml -f compose.cloud.yaml up -d --no-build
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
