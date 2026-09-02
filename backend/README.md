# ImmigrationFlow backend

Phase 2B.1 is the database foundation for ImmigrationFlow. It provides a small FastAPI runtime, PostgreSQL 18.6, four ordered Alembic revisions, fourteen domain tables, database-level integrity and immutability controls, automated tests, CI configuration, and reviewed dependency-update configuration.

There is no Case business API in this phase. The only application endpoints are `/health` and `/health/database`. Phase 2B.2 is the next implementation boundary and has not been implemented.

The project stores schema metadata and synthetic test fixtures only. Do not use real applicant data, identity documents, passport numbers, credentials, or sensitive file bytes.

## Prerequisites

- Docker Desktop, running locally
- [uv](https://docs.astral.sh/uv/)

Run the commands below from the repository root unless a section says otherwise.

## First-time setup

Copy the local environment template. Its database credentials are disposable development/test credentials, not production secrets.

```bash
cp .env.example .env
```

Install the locked backend environment:

```bash
uv sync --project backend --locked --all-groups
```

Start the persistent development database, wait up to 30 seconds for PostgreSQL to accept connections, and then apply all four migrations. The migration command cannot run if the readiness check fails:

```bash
(
set -eu
export ALEMBIC_CONFIG=backend/alembic.ini
export PYTHONPATH=backend
wait_for_development_postgres() {
  readiness_attempt=0
  until docker compose exec -T postgres pg_isready -U immigration_flow -d immigration_flow >/dev/null 2>&1; do
    readiness_attempt=$((readiness_attempt + 1))
    if [ "$readiness_attempt" -ge 30 ]; then
      printf 'PostgreSQL did not become ready within 30 seconds.\n' >&2
      return 1
    fi
    sleep 1
  done
}
docker compose up -d postgres
wait_for_development_postgres
uv run --project backend alembic upgrade head
)
```

Start the API:

```bash
uv run --project backend uvicorn app.main:app --reload --app-dir backend
```

Check the two application endpoints:

- `http://localhost:8000/health` checks the FastAPI process.
- `http://localhost:8000/health/database` checks database connectivity without exposing connection details.

## Database model and migrations

The migration chain is:

1. `0001_identity_and_reference`
2. `0002_case_and_student_pass`
3. `0003_submissions_and_documents`
4. `0004_events_audit_and_immutability`

Together they create fourteen domain tables: `actor`, `applicant_profile`, `institution`, `programme`, `case`, `student_pass_case_profile`, `case_status_history`, `case_submission`, `document`, `document_version`, `submission_document`, `document_check`, `case_event`, and `audit_event`.

Alembic migrations are the only supported way to create or change the database schema. Do not use `Base.metadata.create_all()` or another direct schema-creation shortcut.

## Tests and quality checks

Start the isolated test database. Its data lives in a temporary filesystem and is separate from the persistent development database:

```bash
docker compose --profile test up -d postgres-test
```

Run the complete backend suite from the repository root:

```bash
uv run --project backend pytest backend/tests -v
```

Useful local quality checks are:

```bash
uv run --project backend ruff check backend/app backend/tests backend/migrations
uv run --project backend ruff format --check backend/app backend/tests backend/migrations
uv run --project backend mypy backend/app
```

Integration and migration tests require `TEST_DATABASE_URL` to point to a database whose name ends in `_test`. The checked-in `.env.example` already targets the Compose test service on port 5433. Migration round-trip tests intentionally move only that guarded test database through `base → head → base → head`.

## Safe shutdown and data lifecycle

Stop the development and test containers without deleting the development volume:

```bash
docker compose stop
```

Restarting the development database should preserve its data because `postgres` uses the named `postgres_data` volume.

The following command is destructive and is intentionally separate from normal shutdown. Run it only when you mean to permanently delete the local PostgreSQL volume and rebuild the development database from migrations:

```bash
docker compose down -v
```

## Safe persistence verification

Run this manual check as one shell block on the host after applying migrations. It waits up to 30 seconds for an already-migrated development database before inserting anything. PostgreSQL generates a fresh UUID for the synthetic marker. The shell captures that exact ID, installs cleanup on shell exit, restarts PostgreSQL without removing the volume, waits again, verifies the UUID and marker together, and then deletes only that exact guarded row in a normal transaction:

```bash
(
set -eu
wait_for_development_postgres() {
  readiness_attempt=0
  until docker compose exec -T postgres pg_isready -U immigration_flow -d immigration_flow >/dev/null 2>&1; do
    readiness_attempt=$((readiness_attempt + 1))
    if [ "$readiness_attempt" -ge 30 ]; then
      printf 'PostgreSQL did not become ready within 30 seconds.\n' >&2
      return 1
    fi
    sleep 1
  done
}
docker compose up -d postgres
wait_for_development_postgres
PERSISTENCE_MARKER_ID="$(docker compose exec -T postgres psql -X -Atq -U immigration_flow -d immigration_flow -v ON_ERROR_STOP=1 -c "INSERT INTO actor (actor_type, display_name, external_reference) VALUES ('SYSTEM', 'Synthetic persistence check', 'TASK9-PERSISTENCE-CHECK') RETURNING id;")"
printf 'Generated persistence marker ID: %s\n' "$PERSISTENCE_MARKER_ID"
test -n "$PERSISTENCE_MARKER_ID"
cleanup_persistence_marker() {
  docker compose exec -T postgres psql -X -U immigration_flow -d immigration_flow -v ON_ERROR_STOP=1 -v marker_id="$PERSISTENCE_MARKER_ID" <<'SQL'
BEGIN;
DELETE FROM actor WHERE id = :'marker_id'::uuid AND external_reference = 'TASK9-PERSISTENCE-CHECK';
COMMIT;
SQL
}
trap cleanup_persistence_marker EXIT
docker compose restart postgres
wait_for_development_postgres
docker compose exec -T postgres psql -X -U immigration_flow -d immigration_flow -v ON_ERROR_STOP=1 -v marker_id="$PERSISTENCE_MARKER_ID" <<'SQL'
SELECT id, actor_type, display_name, external_reference
FROM actor
WHERE id = :'marker_id'::uuid
  AND external_reference = 'TASK9-PERSISTENCE-CHECK';
SQL
cleanup_persistence_marker
trap - EXIT
unset PERSISTENCE_MARKER_ID
)
```

The subshell prevents `set -eu` from changing or terminating the parent interactive shell. A readiness failure exits that subshell with a clear error instead of running the next database command. This verification requires the migrations above; an `actor`-table error means migration did not complete and this block must be stopped until the first-time sequence succeeds. The generated UUID is printed before PostgreSQL restarts. The `SELECT` must return exactly one row with that UUID and `TASK9-PERSISTENCE-CHECK`. If verification exits early, the `EXIT` trap attempts the same exact-ID cleanup. If cleanup reports an error, retain the displayed UUID and rerun the guarded `DELETE` after PostgreSQL is available. Do not use `docker compose down -v` during this check.

## Troubleshooting

- If Docker reports that port 5432 or 5433 is occupied, stop the conflicting local database/container before restarting the appropriate Compose service.
- If the bounded readiness check fails, inspect `docker compose ps` and the PostgreSQL container logs, resolve the startup problem, and rerun the complete start/wait/migrate block. Do not continue to the API or persistence check before migrations succeed.
- If `/health` works but `/health/database` returns HTTP 503, confirm `.env` exists, the `postgres` service is healthy, and migrations have run.
- If Alembic or pytest cannot find the backend package, run the documented root-level commands rather than changing Python import paths manually.
- If a migration test refuses a URL, confirm the test database name ends with `_test`; the guard prevents destructive round trips against development databases.
- The current suite can emit one upstream Starlette deprecation warning about `httpx`; it does not indicate a failed test and should be reassessed during dependency updates.

ImmigrationFlow is an independent portfolio project. It is not an official Malaysian immigration service and does not provide legal advice.
