#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="${DEMO_RUNTIME_DIR:-$PROJECT_ROOT/.demo-runtime}"
PID_FILE="$RUNTIME_DIR/pids"
BACKEND_LOG="$RUNTIME_DIR/backend.log"
FRONTEND_LOG="$RUNTIME_DIR/frontend.log"
DATABASE_URL="${DATABASE_URL:-postgresql+psycopg://immigration_flow:immigration_flow_local@localhost:5432/immigration_flow}"

cleanup() {
  if [[ -n "${BACKEND_PID:-}" ]]; then kill "$BACKEND_PID" 2>/dev/null || true; fi
  if [[ -n "${FRONTEND_PID:-}" ]]; then kill "$FRONTEND_PID" 2>/dev/null || true; fi
  rm -f "$PID_FILE"
}

process_fingerprint() {
  local pid="$1"
  local command_line
  local started_at
  command_line="$(ps -p "$pid" -o command= 2>/dev/null || true)"
  started_at="$(ps -p "$pid" -o lstart= 2>/dev/null || true)"
  [[ -n "$command_line" && -n "$started_at" ]] || return 1
  printf '%s\t%s' "$started_at" "$(printf '%s' "$command_line" | cksum | awk '{print $1 ":" $2}')"
}
trap cleanup EXIT INT TERM

command -v docker >/dev/null || { echo "Docker is required." >&2; exit 1; }
command -v uv >/dev/null || { echo "uv is required." >&2; exit 1; }
command -v npm >/dev/null || { echo "Node.js and npm are required." >&2; exit 1; }
docker info >/dev/null 2>&1 || { echo "Docker Desktop must be running." >&2; exit 1; }

mkdir -p "$RUNTIME_DIR"
cd "$PROJECT_ROOT"
docker compose up -d --wait postgres
UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/immigration-flow-uv-cache}" uv sync --project backend --frozen --quiet
if [[ ! -x "$PROJECT_ROOT/apps/immigration-flow-web/node_modules/.bin/vite" ]]; then
  npm --prefix apps/immigration-flow-web ci --silent
fi

export DATABASE_URL DEMO_MODE=true KNOWLEDGE_ACTIVATION_POLL_SECONDS=0
(
  cd backend
  uv run alembic upgrade head
)
GIT_SHA="$(git rev-parse HEAD)"
(
  cd backend
  uv run python -m app.knowledge.cli prepare-demo --root "$PROJECT_ROOT" --git-sha "$GIT_SHA"
)

(
  cd backend
  exec uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
) >"$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!

for _ in {1..60}; do
  if curl --fail --silent http://127.0.0.1:8000/health >/dev/null; then break; fi
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo "Backend failed to start. See .demo-runtime/backend.log." >&2
    exit 1
  fi
  sleep 1
done
curl --fail --silent http://127.0.0.1:8000/health >/dev/null || { echo "Backend health check timed out." >&2; exit 1; }

npm --prefix apps/immigration-flow-web run dev -- --host 127.0.0.1 --port 4173 >"$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!
BACKEND_FINGERPRINT="$(process_fingerprint "$BACKEND_PID")"
FRONTEND_FINGERPRINT="$(process_fingerprint "$FRONTEND_PID")"
printf 'backend\t%s\t%s\nfrontend\t%s\t%s\n' \
  "$BACKEND_PID" "$BACKEND_FINGERPRINT" \
  "$FRONTEND_PID" "$FRONTEND_FINGERPRINT" >"$PID_FILE"
echo "ImmigrationFlow demo: http://127.0.0.1:4173"
wait "$BACKEND_PID" "$FRONTEND_PID"
