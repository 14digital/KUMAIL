# KUMAIL

A private, source-aware intelligence desk. This repository contains a working **foundation MVP**, not the complete production system in the master specification. See [implementation status](docs/STATUS.md) for the exact boundary.

## The listening experience

KUMAIL opens on a single listening screen. Press Play for the latest meaningful edition. Headlines appear as one short paragraph; source links, optional summaries and the written record live behind **Headlines & evidence**. Publisher configuration, history and diagnostics are under the settings control.

A separate editorial worker creates conversational narration from the source evidence. It never sends the written analyst record directly to ElevenLabs. Morning/evening editions target nine minutes, midday four and afternoon six; manual editions target ten. Targets are adjustable under Preferences. Sparse evidence produces a shorter honest edition, never padded content. A headline-only fallback is labelled if OpenAI cannot produce a valid listening script.

Use **Interrupt & ask** or press **M** to pause immediately and speak one question; typing remains available. The current story and briefing are attached to the question. Answers are spoken when ready after that explicit request. **Resume briefing** returns to the saved chapter and position. Supported spoken playback commands include pause, resume briefing, next story and repeat that. The microphone is explicitly activated, browser-dependent and off otherwise; this is not always-listening wake-word detection or full-duplex acoustic barge-in. Browser speech recognition may use an online provider.

Scheduled readiness never starts playback. Audio is chaptered and cached, and long scripts are split without silent truncation. An old report is converted to the listening format when requested; its written evidence is retained.

The [JARVIS brief comparison](docs/KUMAIL_GAP_REVIEW.md) records what is still missing from the autonomous assistant vision.

## All-source collection and listening-based curation

Each enabled approved feed contributes **up to three qualifying new candidates** per run. A feed with too few new items, an invalid date or an access failure is reported honestly. The former eight-article edition cap and two-per-publisher-family cap are removed. Candidates are grouped into distinct developments, with all supporting article links retained; every selected distinct event reaches the listening edition. Editorial generation uses bounded batches, not a hidden final-story limit. Headline previews stay short. Broader coverage may exceed a target duration; nothing is silently dropped to fit ten minutes.

Most RSS feeds do not publish readership metrics. Such items are ranked by relevance and freshness, explicitly labelled. A publisher's actual most-read RSS endpoint can be entered as the optional `popular_rss` field under Sources, on approved domains. Its live feed position and endpoint are retained as provenance; no view counts or cross-publisher popularity comparison are invented. A configured endpoint still depends on that publisher's actual access and ranking contract.

URL/headline rules and optional AI-assisted event grouping consolidate overlapping reports, including paraphrases/languages when the AI grouping succeeds. The partition is validated so no candidate disappears. Similar country or team headlines are protected from simplistic merging. These are grouping heuristics, not independent verification. Materially changed source text is retained rather than suppressed merely because most wording is unchanged.

Questions, repeats, completions, skips and seeks can contribute private inferred signals. At least three different article URLs are required before a bounded topic adjustment is used, with a 30-day half-life. A skip near the end is neutral; forward seeking alone is neutral. Explicit interests stay separate and carry more weight. Settings lets you review, disable or reset this history. Feed coverage remains intact while these signals adjust ordering. Full hierarchical interest learning and semantic cross-edition story timelines remain future work.

**Automatic briefings are off by default**, including on existing installations. Use **Prepare briefing** on the listening screen to generate an edition on demand. Enable the **Automatic briefings** switch to generate editions at 07:00, 11:00, 15:00 and 21:00 Muscat time while the computer is awake and Docker is running. Enabling starts with upcoming slots; it does not catch up earlier editions that day. Scheduled audio consumes ElevenLabs credits even if you do not listen. Disabling stops further automatic audio requests; an already in-flight request may still finish and be charged. Saved audio remains replayable.

When automatic briefings are enabled, upgrading an existing installation may queue one fresh **All-source Intelligence** edition. It does not start playback. The edition may take several minutes to collect, group, edit and narrate.

## Windows: start with Docker Desktop

1. Start Docker Desktop and wait for its engine to run. If it asks for a WSL update, run `wsl --update` in PowerShell and restart Windows.
2. On this GitHub page, select **Code → Download ZIP**, then extract the ZIP in Windows File Explorer.
3. Open the extracted folder and double-click **Start KUMAIL.cmd**.
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

## Audio unavailable after adding ElevenLabs keys

Save `.env` with `ELEVENLABS_API_KEY` and `ELEVENLABS_VOICE_ID`, then run **Update My Intelligence.cmd** so containers load those values. On startup the voice worker queues the latest eligible briefing and latest answer previously marked unavailable. It skips empty news editions and does not replay the whole archive.

For a failed or older report, choose **Generate / Retry audio** under the briefing or in **Read & Verify**. Written content is preserved. The app shows controlled error guidance for invalid keys, permissions, unavailable voices, quota and transient provider errors. Permanent configuration/account errors stop automatic retries; transient failures retry at most four times. No audio plays automatically.

**Operations** reports only whether the voice worker loaded each required variable, never its value. Never share `.env` or key screenshots. Provider errors are classified without storing or displaying their raw response bodies. A configured key is not a verified live connection until narration actually succeeds.

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
