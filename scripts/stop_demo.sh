#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="${DEMO_RUNTIME_DIR:-$PROJECT_ROOT/.demo-runtime}"
PID_FILE="$RUNTIME_DIR/pids"

process_fingerprint() {
  local pid="$1"
  local command_line
  local started_at
  command_line="$(ps -p "$pid" -o command= 2>/dev/null || true)"
  started_at="$(ps -p "$pid" -o lstart= 2>/dev/null || true)"
  [[ -n "$command_line" && -n "$started_at" ]] || return 1
  printf '%s\t%s' "$started_at" "$(printf '%s' "$command_line" | cksum | awk '{print $1 ":" $2}')"
}

if [[ -f "$PID_FILE" ]]; then
  while IFS=$'\t' read -r role pid expected_started expected_checksum; do
    if [[ "$role" =~ ^(backend|frontend)$ && "$pid" =~ ^[0-9]+$ ]]; then
      if actual="$(process_fingerprint "$pid")"; then
        IFS=$'\t' read -r actual_started actual_checksum <<<"$actual"
        if [[ "$actual_started" == "$expected_started" && "$actual_checksum" == "$expected_checksum" ]]; then
          kill "$pid" 2>/dev/null || true
        fi
      fi
    fi
  done < "$PID_FILE"
  rm -f "$PID_FILE"
fi
cd "$PROJECT_ROOT"
if [[ "${DEMO_SKIP_DOCKER_STOP:-false}" != "true" ]]; then
  docker compose stop postgres >/dev/null
fi
echo "ImmigrationFlow demo stopped. PostgreSQL data was preserved."
