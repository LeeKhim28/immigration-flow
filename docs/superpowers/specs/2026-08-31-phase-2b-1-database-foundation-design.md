# Phase 2B.1 Database Foundation Design

**Status:** Approved  
**Date:** 2026-08-31  
**Project:** ImmigrationFlow  
**Depends on:** Phase 2A Student Pass V1 logical ERD and data dictionary

## 1. Objective

Phase 2B.1 translates the approved core portion of the Student Pass V1 logical model into a reproducible PostgreSQL database foundation. It establishes the backend runtime, physical tables, constraints, migrations, health checks, tests, and continuous integration needed before business APIs are introduced.

The phase must prove that the case, Student Pass profile, submission, document, and audit foundations are structurally correct. It does not implement applicant or officer workflows.

## 2. Approved technical choices

| Area | Decision |
|---|---|
| Backend | Python and FastAPI |
| ORM | SQLAlchemy 2.0 typed declarative mappings |
| Database migrations | Alembic |
| Database | PostgreSQL in Docker Compose |
| Database access | Synchronous SQLAlchemy sessions using Psycopg 3 |
| Dependency management | uv with committed `uv.lock` |
| Architecture | Modular monolith |
| Delivery strategy | Phase 2B.1 core case database, followed by Phase 2B.2 knowledge and evaluation database |
| API scope | Health endpoints only; no Case business API |

Synchronous database access is intentional. It keeps transactions, tests, and debugging straightforward at the current portfolio scale. The physical schema does not prevent a later move to asynchronous access if measured demand justifies it.

## 3. Scope

### 3.1 Included

- FastAPI application entry point and configuration
- Synchronous PostgreSQL engine and session lifecycle
- Docker Compose PostgreSQL service with persistent local storage
- Four ordered Alembic migration groups
- Fourteen SQLAlchemy models and their PostgreSQL tables
- Database checks, unique constraints, indexes, foreign keys, and immutability triggers
- `/health` and `/health/database`
- Database integration tests against real PostgreSQL
- GitHub Actions checks
- Automated dependency-update proposals
- Developer setup documentation and safe environment examples

### 3.2 Deferred to Phase 2B.2

- `knowledge_source`, `source_revision`, and knowledge synchronization tables
- Requirement and rule version tables
- Rule assignment and rule evaluation tables
- Case requirements, findings, tasks, and deadlines
- Approval and rule-transition governance tables
- `case.current_rule_set_version_id`
- `case_submission.applicable_rule_set_version_id`
- Automatic re-evaluation after an approved policy transition

The two deferred foreign-key columns are added only when their target tables exist. Phase 2B.1 will not create unvalidated UUID references or skeletal rule tables.

### 3.3 Explicitly out of scope

- Applicant, institution, or officer business APIs
- Authentication, authorization, and complete RBAC
- User interfaces
- Real applicants or production personal information
- Storing real passport or evidence file bytes
- Automated Immigration approval or rejection
- Deployment to a production cloud environment

## 4. Architecture and module boundaries

The backend is one deployable FastAPI application divided by responsibility:

```text
backend/
├── app/
│   ├── main.py
│   ├── core/
│   │   └── configuration and shared application concerns
│   ├── database/
│   │   └── engine, session, base mappings, and shared database types
│   └── domains/
│       ├── cases/
│       ├── student_pass/
│       ├── submissions/
│       └── documents/
├── migrations/
└── tests/
```

Repository-level runtime files include `docker-compose.yml`, `.env.example`, and GitHub workflow/dependency-update configuration. The exact implementation file layout may add focused files within these approved boundaries, but must not introduce repository, service, or API layers that Phase 2B.1 does not use.

Runtime flow:

```text
FastAPI -> SQLAlchemy synchronous Session -> Psycopg 3 -> PostgreSQL
```

Each request or health probe that uses the database receives a bounded session. Successful work commits only when explicitly requested; failures roll back and the session closes. No global mutable session is shared between requests.

## 5. Physical data model

### 5.1 Identity and reference

1. `actor`
   - Minimal reference to applicant, institution worker, officer, administrator, or system actor.
   - Does not implement complete identity or RBAC.
2. `applicant_profile`
   - Applicant context separate from a service-specific case.
   - At most one profile per applicant actor.
   - Phase 2B.1 data is synthetic only.
3. `institution`
   - Education-provider reference with a unique institution code.
4. `programme`
   - Programme owned by an institution.
   - Programme code is unique within its institution.

### 5.2 Case

5. `case`
   - Shared case identity and current workflow state.
   - V1 permits only `STUDENT_PASS` as the service type.
   - `case_number` is unique.
   - `row_version` starts at one and supports future optimistic concurrency checks.
6. `student_pass_case_profile`
   - One-to-one specialization whose primary key is also a foreign key to `case.id`.
   - Holds institution, programme, application, nationality, passport-expiry, location, and arrival facts.
   - A deferred constraint trigger requires every `STUDENT_PASS` case to have exactly one profile by transaction commit and rejects a profile for any other service type.
   - A composite foreign key requires the selected programme to belong to the selected institution.
7. `case_status_history`
   - Append-only record of case status transitions.

### 5.3 Submission and documents

8. `case_submission`
   - Records an `INITIAL` Immigration handover or a `SUPPLEMENTARY` delivery.
   - A partial unique index permits at most one confirmed `INITIAL` submission per case.
   - Confirmation requires `accepted_at`, `immigration_reference`, `receipt_document_version_id`, and `confirmed_at`.
   - The receipt document version must resolve through its document to the same case as the submission.
   - A confirmed `INITIAL` record cannot be updated or deleted.
9. `document`
   - Logical document owned by a case; it contains no file bytes.
10. `document_version`
    - Immutable exact version metadata, including version number, storage reference, content hash, MIME type, size, capture time, and creator.
    - Version number is unique within a document.
11. `submission_document`
    - Links a submission to the exact document version handed over.
    - Composite uniqueness prevents attaching the same version twice for the same purpose.
12. `document_check`
    - Append-only human or automated observation about one document version.
    - It cannot change official case approval state.

### 5.4 Timeline and audit

13. `case_event`
    - Append-only business timeline for a case.
14. `audit_event`
    - Append-only record of who performed or observed an action against an entity.
    - Sensitive values are redacted; this is distinct from application logging.

## 6. PostgreSQL conventions and constraints

- Primary keys use UUIDs.
- Timestamps use timezone-aware PostgreSQL timestamps and are stored in UTC.
- Official policy cutoffs remain interpreted in `Asia/Kuala_Lumpur` unless a policy states otherwise; cutoff evaluation is deferred to Phase 2B.2.
- Python enums provide typed application values. PostgreSQL text columns plus named `CHECK` constraints protect allowed values while keeping future additions migration-friendly.
- Every primary key, foreign key, unique constraint, check constraint, and index has a deterministic name.
- Foreign keys default to restrictive deletion behavior. Cases are archived by state rather than physically deleted.
- Required relationships and values use `NOT NULL` once the record's lifecycle requires them.
- Event payloads and redacted audit summaries may use PostgreSQL `JSONB` where structure varies.
- Indexes support expected foreign-key joins and common case-number, status, submission, and document lookups. Indexes are not added without a defined query or constraint purpose.

### 6.1 Database-enforced invariants

The database, not only future API code, enforces:

1. Unique case numbers and reference codes.
2. One applicant profile per applicant actor.
3. Every Student Pass case has exactly one Student Pass profile at transaction commit, and the profile's programme belongs to its institution.
4. Programme-code uniqueness within an institution.
5. Document-version uniqueness within a document.
6. Submission-document composite uniqueness.
7. At most one confirmed `INITIAL` submission per case.
8. Required evidence fields for confirmed initial submission, including a receipt document version owned by the same case.
9. Append-only behavior for `document_version`, `case_status_history`, `case_event`, `audit_event`, and `document_check`.
10. Immutability of a confirmed `INITIAL` submission.

Reusable PostgreSQL trigger functions protect append-only and confirmation immutability rules. Deferrable constraint triggers protect cross-table lifecycle invariants that cannot be expressed as row-level `CHECK` constraints, so valid multi-row creation can complete within one transaction. Alembic downgrade operations remove dependent triggers before their functions or tables.

Constraints that require Phase 2B.2 entities, including applicable rule-set assignment, are not weakened or simulated in this phase. They become mandatory when those entities are introduced.

## 7. Migration strategy

Alembic migrations are divided into four reviewable groups:

1. Identity and institutional reference tables
2. Case and Student Pass profile tables
3. Submission and document tables
4. Case event, audit, and immutability protections

Each revision includes an explicit `upgrade()` and `downgrade()`. The verified migration path is:

```text
empty database
-> upgrade to head
-> downgrade one revision at a time to base
-> upgrade to head again
-> confirm the same expected schema and constraints
```

PostgreSQL transactional DDL is used so a failed revision does not intentionally leave a partially applied structure. Data-destructive migrations are outside Phase 2B.1.

## 8. Configuration, secrets, and local data

- `.env.example` documents required variables using non-sensitive demonstration values.
- `.env`, database volumes, virtual environments, caches, and local test artifacts remain ignored by Git.
- Database credentials come from environment settings and are never embedded in source files, logs, health responses, or exceptions returned to clients.
- Docker Compose uses a named volume so an ordinary container restart preserves local data.
- Test execution uses a separate disposable database and cannot target the normal development database accidentally.
- Repository fixtures use synthetic identifiers and synthetic personal data only.
- PostgreSQL stores document metadata, hashes, and storage references, not real sensitive files.

## 9. Health checks and failure behavior

### `/health`

- Reports that the FastAPI process is running.
- Does not require a database query.
- Returns no environment details or secrets.

### `/health/database`

- Executes a minimal database connectivity query.
- Returns success when PostgreSQL responds.
- Returns HTTP 503 when PostgreSQL is unavailable.
- Logs a sanitized diagnostic for developers without returning credentials, the full connection URL, or raw database exceptions.

Database exceptions roll back the current session. Migration failures stop the migration command. The application does not silently create schema objects at startup; Alembic is the only schema-change mechanism.

## 10. Dependency and version policy

- Python uses the stable 3.14 series.
- PostgreSQL uses the supported 18 series and tracks its current minor release.
- FastAPI, SQLAlchemy 2.0, Alembic, Psycopg 3, testing tools, and quality tools are resolved to mutually compatible stable releases during implementation.
- `pyproject.toml` declares supported ranges; `uv.lock` records the exact tested resolution and is committed.
- CI installs with the lockfile in locked mode.
- Dependabot checks uv, Docker, and GitHub Actions dependencies weekly.
- Dependency PRs are never automatically merged. They must pass all checks and receive human review.
- Major upgrades require a deliberate compatibility review and, where relevant, a migration rehearsal.

This policy balances reproducibility with updates: the repository records an exact known-good environment while automation proposes newer versions for validation.

## 11. Test strategy

### 11.1 Fast unit checks

- Configuration accepts valid settings and rejects missing required settings.
- SQLAlchemy metadata contains expected named tables and constraints.
- Enum and shared-type behavior is deterministic.
- `/health` responds without requiring PostgreSQL.

### 11.2 PostgreSQL integration tests

Tests use real PostgreSQL rather than SQLite because partial indexes, `JSONB`, timezone behavior, and triggers are PostgreSQL-specific. They cover:

- all fourteen tables and approved relationships;
- valid insert paths for each domain;
- foreign-key, check, uniqueness, and not-null failures;
- one confirmed `INITIAL` submission per case;
- confirmation evidence requirements;
- append-only tables rejecting update and delete operations;
- confirmed initial submissions rejecting update and delete operations;
- UUID and timezone-aware timestamp behavior;
- persistent Docker volume behavior through documented manual verification.

### 11.3 Migration tests

- Upgrade an empty test database to head.
- Validate the expected tables, constraints, indexes, functions, and triggers.
- Downgrade revision by revision to base.
- Upgrade to head again and repeat structural validation.

### 11.4 Existing knowledge-base regression

The existing Student Pass knowledge-base validator and policy-contract tests continue to run. Phase 2B.1 must not reduce Phase 1 or Phase 2A validation coverage.

## 12. Continuous integration

Every pull request and push to the default branch runs GitHub Actions on a Linux runner:

1. Check out the repository.
2. Prepare the approved Python series and uv.
3. Install exactly from `uv.lock` in locked mode.
4. Run formatting, lint, and static-type checks.
5. Start a temporary PostgreSQL service container and wait for its health check.
6. Run Alembic migration round-trip tests.
7. Run FastAPI and database tests.
8. Run the existing knowledge-base and policy-contract validation.

No repository or production secret is required. CI uses disposable database credentials scoped to the workflow.

## 13. Developer experience and manual prerequisites

The developer manually installs and starts:

1. Docker Desktop
2. uv

The repository then documents a short workflow to:

1. synchronize the locked Python environment;
2. start PostgreSQL;
3. apply Alembic migrations;
4. run FastAPI;
5. run the full test suite;
6. stop services without deleting the persistent volume.

No separate manual PostgreSQL or Python installation is required when uv can provide the requested Python series.

## 14. Acceptance criteria

Phase 2B.1 is complete only when:

1. A clean machine with Docker Desktop and uv can reproduce the documented environment.
2. PostgreSQL starts with a health check and persistent development volume.
3. FastAPI starts and both health endpoints behave as specified.
4. All fourteen approved tables exist with their declared relationships and constraints.
5. The four migration groups upgrade, downgrade, and re-upgrade successfully.
6. Every critical invariant has both a passing and a rejecting integration test.
7. Immutable records cannot be updated or deleted through direct SQL.
8. GitHub Actions passes the backend and existing knowledge-base suites.
9. Dependabot is configured to propose reviewed dependency updates.
10. No secret, production personal data, or real sensitive document is committed.
11. No Case business API or automated official decision is introduced.

## 15. Implementation boundary

Approval of this document authorizes preparation of a separate implementation plan. It does not itself authorize unplanned Phase 2B.2 rule synchronization, policy activation, re-evaluation behavior, business APIs, authentication, UI work, or production deployment.

## 16. Authoritative technical references

- [PostgreSQL versioning policy](https://www.postgresql.org/support/versioning/)
- [SQLAlchemy 2.0 documentation](https://docs.sqlalchemy.org/en/20/)
- [uv project and lockfile structure](https://docs.astral.sh/uv/concepts/projects/layout/)
- [uv Python version management](https://docs.astral.sh/uv/concepts/python-versions/)
- [GitHub Dependabot supported ecosystems](https://docs.github.com/en/code-security/reference/supply-chain-security/supported-ecosystems-and-repositories)
- [GitHub Actions PostgreSQL service containers](https://docs.github.com/en/actions/tutorials/use-containerized-services/create-postgresql-service-containers)
