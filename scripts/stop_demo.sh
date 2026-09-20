#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="$PROJECT_ROOT/.demo-runtime/pids"

if [[ -f "$PID_FILE" ]]; then
  while IFS= read -r pid; do
    if [[ "$pid" =~ ^[0-9]+$ ]]; then kill "$pid" 2>/dev/null || true; fi
  done < "$PID_FILE"
  rm -f "$PID_FILE"
fi
cd "$PROJECT_ROOT"
docker compose stop postgres >/dev/null
echo "ImmigrationFlow demo stopped. PostgreSQL data was preserved."
