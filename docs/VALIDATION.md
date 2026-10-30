# Validation record

Executed in the current cloud machine:

- `uv sync --frozen`: installed the locked Python environment.
- `pytest -q`: 16 passed. One FastAPI/Starlette test-client deprecation warning; no skipped tests.
- `npm run build`: production compilation, TypeScript validation and page generation passed.
- `npm audit --audit-level=moderate`: zero reported vulnerabilities after overriding PostCSS to the patched 8.5.23 series.
- `scripts/smoke.py`: actual HTTP authentication, authorised document ingestion, queued research completion, matching provenance, deletion, dashboard rendering and BFF routing passed against running local processes.
- Non-root API and Next.js containers passed authenticated gateway routing on a temporary private Docker network; validation containers and network were removed.
- Backend and frontend Docker builds succeeded with TLS verification and managed-cloud CA trust. The frontend was rebuilt after the dependency audit fix.

Controlled fixtures are confined to tests. No live publisher, paid-provider, YouTube, Instagram, Audible or Blinkist connection was claimed or validated. No automated browser tests ran. All tests cover only the implemented foundation; the complete master-spec acceptance suite is outstanding.

The development process group was started with `scripts/dev.sh`. Its random access key is in ignored `.env` and was never printed. No remote push, environment publication or deployment to a public host was performed.

## KUMAIL listening release

- 44 backend tests passed, including separate editorial/audio queues, spoken-script attribution, legacy report conversion, no silent script truncation, preserved written evidence, context-bound questions, reserved answer capacity, lease fencing and safe provider failures.
- Next.js production compilation, TypeScript validation and static page generation passed.
- Production-build Chromium acceptance passed with controlled local feed/audio/answer fixtures: no login or scheduled autoplay, immediate interruption, exact current-story context, spoken answer, saved-position resume, explicit microphone activation, a simulated spoken command, navigation across a split story, optional written evidence and a mobile layout without horizontal overflow.
- 39 PowerShell updater checks passed. The old updater remains usable; KUMAIL-named aliases contain the same implementation.
- Compose configuration was checked for the independent editorial worker, shared backend image and unchanged existing data volume.

Browser audio fixtures are deliberately test-only WAV data, not a claimed ElevenLabs response. Speech recognition was simulated for deterministic browser tests. No live OpenAI/ElevenLabs request, actual Windows microphone test, always-on host deployment or notification delivery is claimed for this release. Listening duration and voice naturalness still need live acceptance with the user's approved sources and chosen voice.

## All-source curation update

- 62 backend tests passed: per-feed quotas, no global eight-story cap, a full 15-item collection-to-listening path, a 21-story edition, cross-publisher grouping, invalid-partition fallback, different-country/team safeguards, material-change retention, publisher-feed rank provenance, idempotent feedback, repeated-signal thresholds, decay, neutral forward seeks, opt-out/reset and actual effect on subsequent ranking.
- Production Next.js build and TypeScript checks passed.
- Chromium production acceptance retained playback/interruption/resume behaviour and confirmed skip/replay feedback requests carry the correct story IDs.
- One-time automatic preparation after the curation upgrade was tested for idempotency.

No live publisher popularity endpoint or live semantic-grouping quality is claimed from controlled tests. The supplied ordinary RSS feeds are not re-labelled as most-read feeds. Semantic event grouping remains model-assisted when configured, with conservative fallbacks.
