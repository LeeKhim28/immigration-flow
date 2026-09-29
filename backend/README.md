# ImmigrationFlow backend

Phase 2B provides the knowledge, governance, and synthetic Student Pass workflow foundation; Phase 3 exposes it through the portfolio demo. The backend uses PostgreSQL 18.6, nine ordered Alembic revisions, immutable source/requirement/rule/evaluation history, atomic synchronization, administrator approval, locked activation, monitoring, and automated tests.

The business API is intentionally narrow. It demonstrates case workflow and auditability; it does not integrate with Immigration, make decisions, upload documents, or authenticate real users.

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

Start the persistent development database, wait up to 30 seconds for PostgreSQL to accept connections, and then apply all seven migrations. The migration command cannot run if the readiness check fails:

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

## Synthetic Student Pass workflow API

The API accepts an existing synthetic actor UUID in `X-Actor-Id`. This header is a deliberate demo boundary, not authentication; do not expose it in a public deployment. Seed synthetic actors, applicant profiles, institutions, and programmes through test/demo fixtures before calling these routes.

1. `POST /api/v1/applicant/cases` creates a `DRAFT` Student Pass case and profile. The actor must own `applicant_profile_id`.
2. `POST /api/v1/applicant/cases/{case_id}/submit` records `submitted_at` and changes the case to `SUBMITTED`. It represents handover, not official acceptance or approval.
3. `POST /api/v1/applicant/cases/{case_id}/documents` records one synthetic document's immutable metadata and first version for the case owner while the case is still `DRAFT`. It does not accept or store file bytes; `storage_reference` must use the `metadata-only://` demo scheme.
4. `GET /api/v1/officer/cases?status=SUBMITTED` lists the officer queue.
5. `POST /api/v1/officer/cases/{case_id}/start-processing` assigns the case to an officer and changes it to `IN_PROCESS`.
6. `GET /api/v1/applicant/cases/{case_id}/checklist` previews the current applicable requirements for a draft without assigning them; after handover it returns the case's fixed semantic rule-set version and materialized requirements.

At handover, the transaction selects the newest applicable `ACTIVE` Student Pass release by `submitted_at`, records an immutable rule assignment, and materializes its source-traceable requirements as `PENDING` checklist entries. A missing eligible release blocks the submission and leaves the case in `DRAFT`. Every transition creates a status-history row, a case event, and an audit event in the same transaction. `accepted_at` remains separate: it may only be populated later with official evidence, whereas `submitted_at` records the applicant’s completed handover.

## Database model and migrations

The migration chain is:

1. `0001_identity_and_reference`
2. `0002_case_and_student_pass`
3. `0003_submissions_and_documents`
4. `0004_events_audit_and_immutability`
5. `0005_knowledge_sources_and_requirements`
6. `0006_rule_versions_and_activation`
7. `0007_submission_handover_timestamp`
8. `0008_case_rule_assignments_and_requirements`
9. `0009_rule_evaluations_and_findings`

Together they create the platform, knowledge, and governance tables. The knowledge release path adds `knowledge_sync_run`, `knowledge_source`, `source_revision`, `requirement`, `requirement_version`, `requirement_source`, `rule_set`, `rule_set_version`, `rule_definition`, `rule_version`, `rule_requirement`, and `approval_event`.

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

## Knowledge release operations

The source monitor is intentionally separate from formal synchronization. A
monitor can report a changed official page and create or update a review issue,
but it cannot mutate PostgreSQL rules.

From a clean checkout, validate and synchronize an explicit commit:

```bash
ruby scripts/validate_knowledge_base.rb
uv run --project backend python -m app.knowledge.cli sync --root . --git-sha "$(git rev-parse HEAD)"
```

After inspecting the generated release, submit it for review and record a
decision with the `review` and `decide` CLI subcommands. Only an
`ADMINISTRATOR` actor can approve or reject. Activation is separate and
time-bound:

```bash
uv run --project backend python -m app.knowledge.cli activate-due --at 2026-09-18T00:00:00+08:00
```

The CLI uses exit code 0 for success, 2 for repository/validation failures, and
3 for database failures. Errors are bounded and do not print connection
details, secrets, source bodies, or applicant data. The FastAPI lifespan
performs one activation catch-up and can run a cancellable poller when
`KNOWLEDGE_ACTIVATION_POLL_SECONDS` is positive.

For public use, replace local Docker with a persistent managed PostgreSQL
database, managed secrets, backups, monitoring, and an independently
supervised worker. The local Compose stack is a development/demo dependency,
not an always-on production deployment.

Integration and migration tests require `TEST_DATABASE_URL` to point to a database whose name ends in `_test`. `make test` uses an isolated local port (55433 by default) and runs migrations before the suite. Migration round-trip tests intentionally move only that guarded test database through the tested revision sequence.

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
