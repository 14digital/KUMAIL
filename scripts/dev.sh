#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -f .env ]; then
  echo 'Create .env using .env.example and set a random APP_TOKEN of at least 32 characters.' >&2
  exit 1
fi
set -a
source .env
set +a
export PYTHONPATH="$PWD/backend"
pids=()
cleanup() { for pid in "${pids[@]}"; do kill "$pid" 2>/dev/null || true; done; }
trap cleanup EXIT INT TERM
.venv/bin/uvicorn intelligence.api:app --host 0.0.0.0 --port 8000 & pids+=("$!")
for role in scheduler news voice research deep opportunities; do
  SERVICE_ROLE="$role" .venv/bin/python -m intelligence.worker & pids+=("$!")
done
(cd web && npm run dev) & pids+=("$!")
wait -n
