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
