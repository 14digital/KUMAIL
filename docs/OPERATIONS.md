# Security, deployment and recovery

## Before private production use

Use TLS at a reverse proxy; restrict ingress to the single authorised user. The current bearer key is a bootstrap authentication mechanism, not a complete identity platform. Set a unique random `APP_TOKEN` in a private environment/secret manager; rotate by replacing it and restarting API and clients. Never paste keys into commits or chat. Add rate limiting at the proxy. No account tokens are stored by the app.

All API data endpoints and audio require authentication. Source URLs require approved public HTTPS domains and reject credentials, nonstandard ports and private addresses. Redirects are not followed. DNS checks are defence in depth; enforce outbound destination restrictions at your deployment proxy to prevent DNS rebinding. Do not approve untrusted endpoints or private hosts. External feed content is stripped of HTML and rendered as escaped text. AI prompts treat content as untrusted evidence and receive bounded excerpts. This reduces prompt-injection risk but is not a complete formal security guarantee. AI output cannot execute tools or modify source permissions.

The browser's optional speech recogniser may use the browser vendor's cloud; choose text input for confidential questions. Document excerpts can be sent to OpenAI when configured. Keep provider data-processing requirements in mind.

Do not enable public Next.js dev mode. Use `npm run build` and `npm start` behind TLS. The Compose web image builds the correct API hostname; a different production API hostname requires rebuilding with `API_URL`.

## Recovery and backups

Each service can be restarted independently, e.g. `docker compose restart voice`. Stop all writers before a filesystem-level backup of the data volume, or use SQLite's backup API for every database. Include audio files and private configuration separately; encrypt backups and test restoration. A copying backup of live WAL databases is unsafe.

Expired broker leases are reclaimed after restart. Failed jobs back off and become dead after four attempts. Inspect `/api/operations` for error types. There is no automatic dead-letter replay endpoint; diagnose the provider/configuration failure before an operator-controlled replay. Do not delete the broker database to retry jobs: that loses idempotency keys.

For local development, `scripts/dev.sh` owns and cleans up only the processes it starts. On shared environments do not use broad process-kill commands. In cloud tasks use the existing checkout; do not create a Git worktree unless explicitly requested. Running processes do not survive an environment snapshot. Restart with the script after restoration; retained dependencies and files are distinct from running services.

The current host and shared volume are single failure points. Keep an off-host encrypted backup. A host restore needs all domain databases, broker idempotency history and audio assets together. Full cross-domain consistency and service-owned database permissions require the production migration described in the architecture document.
