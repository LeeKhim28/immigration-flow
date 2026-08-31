# Phase 2B.1 Database Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reproducible, migration-managed PostgreSQL foundation for the approved ImmigrationFlow Student Pass V1 core case, submission, document, and audit model without adding business APIs.

**Architecture:** Implement one synchronous FastAPI modular monolith under `backend/`, using typed SQLAlchemy 2.0 mappings, Psycopg 3, and four ordered Alembic migrations. Docker Compose supplies separate persistent development and disposable test PostgreSQL services; PostgreSQL constraints and triggers enforce invariants even when writes bypass Python.

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy 2.0, Alembic, Psycopg 3, PostgreSQL 18, Docker Compose, uv, pytest, Ruff, mypy, GitHub Actions, Dependabot

**Spec:** `docs/superpowers/specs/2026-08-31-phase-2b-1-database-foundation-design.md`

## Global Constraints

- Python uses the stable 3.14 series.
- PostgreSQL uses the supported 18 series and tracks its current minor release.
- Database access is synchronous through SQLAlchemy sessions and Psycopg 3.
- `pyproject.toml` declares compatible dependency ranges; committed `uv.lock` records exact tested versions.
- Store timezone-aware timestamps in UTC. Interpret later official policy cutoffs in `Asia/Kuala_Lumpur` unless policy states otherwise.
- Use UUID primary keys, deterministically named constraints, and restrictive foreign-key deletion behavior.
- Use Python enums plus PostgreSQL text columns with named `CHECK` constraints.
- Alembic is the only schema-change mechanism; the application must not call `metadata.create_all()`.
- Only `/health` and `/health/database` are allowed. Do not add Case business APIs.
- Use synthetic fixtures only. Never commit secrets, production personal data, real passports, or real evidence files.
- No rule, model, endpoint, or test may represent automated Immigration approval or rejection.
- Keep Phase 2B.2 rule synchronization, applicability, and re-evaluation behavior out of this implementation.
- Complete each task's red-green-refactor cycle and commit before starting the next task.

---

## Planned file structure

```text
immigration-flow/
├── .env.example
├── .github/
│   ├── dependabot.yml
│   └── workflows/backend-ci.yml
├── docker-compose.yml
├── README.md
└── backend/
    ├── .python-version
    ├── README.md
    ├── alembic.ini
    ├── pyproject.toml
    ├── uv.lock
    ├── app/
    │   ├── __init__.py
    │   ├── main.py
    │   ├── health.py
    │   ├── core/
    │   │   ├── __init__.py
    │   │   └── config.py
    │   ├── database/
    │   │   ├── __init__.py
    │   │   ├── base.py
    │   │   ├── enums.py
    │   │   ├── models.py
    │   │   └── session.py
    │   └── domains/
    │       ├── __init__.py
    │       ├── identity/models.py
    │       ├── institutions/models.py
    │       ├── cases/models.py
    │       ├── student_pass/models.py
    │       ├── submissions/models.py
    │       └── documents/models.py
    ├── migrations/
    │   ├── env.py
    │   ├── script.py.mako
    │   └── versions/
    │       ├── 0001_identity_and_reference.py
    │       ├── 0002_case_and_student_pass.py
    │       ├── 0003_submissions_and_documents.py
    │       └── 0004_events_audit_and_immutability.py
    └── tests/
        ├── conftest.py
        ├── unit/
        │   ├── test_config.py
        │   └── test_health.py
        ├── integration/
        │   ├── test_database_health.py
        │   ├── test_identity_reference_schema.py
        │   ├── test_case_schema.py
        │   ├── test_submission_document_schema.py
        │   └── test_append_only_schema.py
        └── migration/
            └── test_migration_round_trip.py
```

Each domain model file owns only its mapped classes. `app/database/models.py` imports those modules solely to expose one complete `Base.metadata` to Alembic. Cross-table PostgreSQL functions and triggers live in the migration that introduces or finalizes the invariant.

---

### Task 1: Reproducible Python and Docker runtime

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/.python-version`
- Create: `backend/uv.lock`
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/app/health.py`
- Create: `backend/app/core/__init__.py`
- Create: `backend/app/core/config.py`
- Create: `backend/tests/unit/test_config.py`
- Create: `backend/tests/unit/test_health.py`
- Create: `docker-compose.yml`
- Create: `.env.example`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `get_settings() -> Settings`
- Produces: `create_app() -> FastAPI`
- Produces: `GET /health -> {"status": "ok"}` without querying PostgreSQL
- Produces: Docker services `postgres` on port 5432 and profile-gated `postgres-test` on port 5433
- Consumes: no earlier Phase 2B implementation

- [ ] **Step 1: Write failing configuration and process-health tests**

```python
# backend/tests/unit/test_config.py
from app.core.config import Settings


def test_settings_reject_an_empty_database_url() -> None:
    try:
        Settings(database_url="", app_env="test")
    except ValueError:
        return
    raise AssertionError("empty database_url must be rejected")
```

```python
# backend/tests/unit/test_health.py
from fastapi.testclient import TestClient
from app.main import create_app


def test_process_health_does_not_require_database() -> None:
    response = TestClient(create_app()).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: Run the tests and verify the expected import failure**

Run:

```bash
cd backend
uv run pytest tests/unit/test_config.py tests/unit/test_health.py -v
```

Expected: FAIL because `pyproject.toml` and the application modules do not exist.

- [ ] **Step 3: Create the uv project and lock the runtime dependencies**

Create `backend/.python-version` containing `3.14`. Create `backend/pyproject.toml` with:

```toml
[project]
name = "immigration-flow-backend"
version = "0.1.0"
requires-python = ">=3.14,<3.15"
dependencies = [
  "alembic>=1.16,<2",
  "fastapi>=0.136,<1",
  "psycopg[binary]>=3.2,<4",
  "pydantic-settings>=2.10,<3",
  "sqlalchemy>=2.0.52,<3",
  "uvicorn[standard]>=0.35,<1",
]

[dependency-groups]
dev = [
  "httpx>=0.28,<1",
  "mypy>=1.17,<2",
  "pytest>=9,<10",
  "pytest-cov>=7.1,<8",
  "ruff>=0.16,<1",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra --strict-markers"

[tool.ruff]
target-version = "py314"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]

[tool.mypy]
python_version = "3.14"
strict = true
packages = ["app"]
```

Run `uv lock` from `backend/` and commit the generated `backend/uv.lock`.

- [ ] **Step 4: Implement minimal settings and `/health`**

```python
# backend/app/core/config.py
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    app_env: str = "development"
    database_url: str = Field(min_length=1)
    test_database_url: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
```

```python
# backend/app/health.py
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def process_health() -> dict[str, str]:
    return {"status": "ok"}
```

```python
# backend/app/main.py
from fastapi import FastAPI
from app.health import router as health_router


def create_app() -> FastAPI:
    app = FastAPI(title="ImmigrationFlow API", version="0.1.0")
    app.include_router(health_router)
    return app


app = create_app()
```

- [ ] **Step 5: Add separate development and test PostgreSQL services**

Create `docker-compose.yml` with `postgres:18.6`, a health check using `pg_isready`, a named `postgres_data` volume for development, and a `postgres-test` service under the `test` profile using a `tmpfs` data directory. Use database names `immigration_flow` and `immigration_flow_test`; never reuse the development URL in tests.

```yaml
services:
  postgres:
    image: postgres:18.6
    environment:
      POSTGRES_DB: immigration_flow
      POSTGRES_USER: immigration_flow
      POSTGRES_PASSWORD: immigration_flow_local
    ports: ["5432:5432"]
    volumes: ["postgres_data:/var/lib/postgresql"]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U immigration_flow -d immigration_flow"]
      interval: 5s
      timeout: 5s
      retries: 10

  postgres-test:
    image: postgres:18.6
    profiles: ["test"]
    environment:
      POSTGRES_DB: immigration_flow_test
      POSTGRES_USER: immigration_flow
      POSTGRES_PASSWORD: immigration_flow_test
    ports: ["5433:5432"]
    tmpfs: ["/var/lib/postgresql"]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U immigration_flow -d immigration_flow_test"]
      interval: 2s
      timeout: 3s
      retries: 15

volumes:
  postgres_data:
```

- [ ] **Step 6: Add safe environment examples and ignores**

Create `.env.example` with the two local URLs. Add `.env`, `.venv/`, `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, coverage artifacts, and local PostgreSQL artifacts to `.gitignore` without deleting existing rules.

- [ ] **Step 7: Run unit and configuration checks**

Run:

```bash
cd backend
DATABASE_URL=postgresql+psycopg://example:example@localhost/example uv run pytest tests/unit -v
uv run ruff check app tests
uv run mypy app
```

Expected: all commands PASS.

- [ ] **Step 8: Commit the reproducible runtime**

```bash
git add .env.example .gitignore docker-compose.yml backend
git commit -m "build: initialize FastAPI and PostgreSQL runtime"
```

---

### Task 2: Synchronous database sessions and database health

**Files:**
- Create: `backend/app/database/__init__.py`
- Create: `backend/app/database/base.py`
- Create: `backend/app/database/session.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/integration/test_database_health.py`
- Modify: `backend/app/health.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Consumes: `Settings.database_url`
- Produces: `class Base(DeclarativeBase)`
- Produces: `build_engine(database_url: str) -> Engine`
- Produces: `build_session_factory(engine: Engine) -> sessionmaker[Session]`
- Produces: `get_db_session() -> Iterator[Session]`
- Produces: `assert_test_database_url(database_url: str) -> None`
- Produces: `GET /health/database` with 200 on `SELECT 1` and 503 on connection failure

- [ ] **Step 1: Write failing session-safety and database-health tests**

```python
def test_test_database_guard_rejects_development_database() -> None:
    with pytest.raises(ValueError, match="_test"):
        assert_test_database_url(
            "postgresql+psycopg://immigration_flow:x@localhost/immigration_flow"
        )


def test_database_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health/database")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: Start disposable PostgreSQL and verify failure**

Run:

```bash
docker compose --profile test up -d postgres-test
cd backend
TEST_DATABASE_URL=postgresql+psycopg://immigration_flow:immigration_flow_test@localhost:5433/immigration_flow_test uv run pytest tests/integration/test_database_health.py -v
```

Expected: FAIL because the database session and endpoint are not implemented.

- [ ] **Step 3: Implement the shared declarative base and synchronous session factory**

```python
# backend/app/database/base.py
from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
```

```python
# backend/app/database/session.py
from collections.abc import Iterator
from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker


def assert_test_database_url(database_url: str) -> None:
    database = make_url(database_url).database or ""
    if not database.endswith("_test"):
        raise ValueError("test database name must end with _test")


def build_engine(database_url: str) -> Engine:
    return create_engine(database_url, pool_pre_ping=True)


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
```

Implement the FastAPI dependency so it rolls back on exceptions and always closes the session.

- [ ] **Step 4: Implement sanitized database health behavior**

Execute `select(1)` inside a bounded session. Catch `SQLAlchemyError`, log only the exception class plus a fixed message, and return `HTTPException(status_code=503, detail="database unavailable")`. Never return or log the database URL.

- [ ] **Step 5: Run database-health and unit tests**

```bash
cd backend
TEST_DATABASE_URL=postgresql+psycopg://immigration_flow:immigration_flow_test@localhost:5433/immigration_flow_test uv run pytest tests/unit tests/integration/test_database_health.py -v
```

Expected: PASS, including a test that overrides the session dependency with a failing session and asserts the 503 body contains no connection string.

- [ ] **Step 6: Commit the database session boundary**

```bash
git add backend/app backend/tests
git commit -m "feat: add synchronous database health boundary"
```

---

### Task 3: Migration 0001 — identity and institutional reference

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/migrations/env.py`
- Create: `backend/migrations/script.py.mako`
- Create: `backend/migrations/versions/0001_identity_and_reference.py`
- Create: `backend/app/database/enums.py`
- Create: `backend/app/database/models.py`
- Create: `backend/app/domains/__init__.py`
- Create: `backend/app/domains/identity/__init__.py`
- Create: `backend/app/domains/identity/models.py`
- Create: `backend/app/domains/institutions/__init__.py`
- Create: `backend/app/domains/institutions/models.py`
- Create: `backend/tests/integration/test_identity_reference_schema.py`

**Interfaces:**
- Consumes: `Base.metadata` and test database URL safety guard
- Produces: `Actor`, `ApplicantProfile`, `Institution`, `Programme`
- Produces tables: `actor`, `applicant_profile`, `institution`, `programme`
- Produces enum values: `ActorType={APPLICANT, INSTITUTION_WORKER, OFFICER, ADMINISTRATOR, SYSTEM}`
- Produces revision `0001_identity_and_reference` with `down_revision = None`

Exact persisted fields:

```text
actor: id UUID, actor_type TEXT, display_name TEXT, external_reference TEXT NULL,
       created_at TIMESTAMPTZ, updated_at TIMESTAMPTZ
applicant_profile: id UUID, actor_id UUID, synthetic_reference TEXT,
                   created_at TIMESTAMPTZ, updated_at TIMESTAMPTZ
institution: id UUID, institution_code TEXT, name TEXT, institution_type TEXT,
             region_code TEXT, active BOOLEAN
programme: id UUID, institution_id UUID, programme_code TEXT, name TEXT,
           level TEXT, active BOOLEAN
```

- [ ] **Step 1: Write failing identity/reference constraint tests**

Test valid inserts plus these rejecting cases:

```python
with pytest.raises(IntegrityError):
    session.add(Actor(actor_type="UNKNOWN", display_name="Invalid"))
    session.commit()

with pytest.raises(IntegrityError):
    session.add_all([
        ApplicantProfile(actor_id=applicant.id, synthetic_reference="SYN-001"),
        ApplicantProfile(actor_id=applicant.id, synthetic_reference="SYN-002"),
    ])
    session.commit()
```

Also reject duplicate `institution_code`, duplicate `synthetic_reference`, and duplicate `(institution_id, programme_code)`.

- [ ] **Step 2: Run the migration test and verify it fails**

```bash
cd backend
TEST_DATABASE_URL=postgresql+psycopg://immigration_flow:immigration_flow_test@localhost:5433/immigration_flow_test uv run pytest tests/integration/test_identity_reference_schema.py -v
```

Expected: FAIL because the models and migration do not exist.

- [ ] **Step 3: Configure Alembic to import application metadata and runtime URL**

`migrations/env.py` must import `app.database.models` before assigning `target_metadata = Base.metadata`. Read `DATABASE_URL` from settings, replace Alembic's configured URL, enable `compare_type=True`, and render migrations inside a transaction. Do not call `create_all()`.

- [ ] **Step 4: Implement typed mappings and named constraints**

Use SQLAlchemy `Mapped[...]` and `mapped_column(...)`. Use server-side `gen_random_uuid()` and `now()` defaults. Add:

```python
UniqueConstraint("institution_id", "programme_code", name="uq_programme_institution_code")
UniqueConstraint("id", "institution_id", name="uq_programme_id_institution")
CheckConstraint(
    "actor_type IN ('APPLICANT','INSTITUTION_WORKER','OFFICER','ADMINISTRATOR','SYSTEM')",
    name="actor_type_allowed",
)
```

`app/database/models.py` imports all four model classes and exports `Base` so migration metadata is complete.

- [ ] **Step 5: Write migration 0001 explicitly**

Create tables in foreign-key order: `actor`, `applicant_profile`, `institution`, `programme`. Downgrade in reverse order. Match model column types, nullability, names, checks, unique constraints, and indexes exactly.

- [ ] **Step 6: Apply 0001 and run tests**

```bash
cd backend
DATABASE_URL=postgresql+psycopg://immigration_flow:immigration_flow_test@localhost:5433/immigration_flow_test uv run alembic upgrade 0001_identity_and_reference
TEST_DATABASE_URL=postgresql+psycopg://immigration_flow:immigration_flow_test@localhost:5433/immigration_flow_test uv run pytest tests/integration/test_identity_reference_schema.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit migration 0001**

```bash
git add backend/alembic.ini backend/migrations backend/app/database backend/app/domains backend/tests/integration/test_identity_reference_schema.py
git commit -m "feat: add identity and institution schema"
```

---

### Task 4: Migration 0002 — generic Case and Student Pass profile

**Files:**
- Create: `backend/migrations/versions/0002_case_and_student_pass.py`
- Create: `backend/app/domains/cases/__init__.py`
- Create: `backend/app/domains/cases/models.py`
- Create: `backend/app/domains/student_pass/__init__.py`
- Create: `backend/app/domains/student_pass/models.py`
- Create: `backend/tests/integration/test_case_schema.py`
- Modify: `backend/app/database/enums.py`
- Modify: `backend/app/database/models.py`

**Interfaces:**
- Consumes: `Actor`, `ApplicantProfile`, `Institution`, `Programme`
- Produces: `ImmigrationCase` mapped to quoted table name `case`
- Produces: `StudentPassCaseProfile`, `CaseStatusHistory`
- Produces revision `0002_case_and_student_pass` with down revision `0001_identity_and_reference`

Persisted enum values:

```text
ServiceType: STUDENT_PASS
CaseStatus: DRAFT, SUBMITTED, IN_PROCESS, ACTION_REQUIRED, COMPLETED, WITHDRAWN
CaseStage: PRE_SUBMISSION, IMMIGRATION_PROCESSING, POST_ARRIVAL, CLOSED
ApplicationType: NEW
InstitutionType: UA, IPTS
ApplicantLocation: OUTSIDE_MALAYSIA
```

Exact fields:

```text
case: id, case_number, applicant_profile_id, service_type, status, stage,
      created_by_actor_id, assigned_to_actor_id NULL, created_at, updated_at, row_version
student_pass_case_profile: case_id PK/FK, application_type, institution_id, programme_id,
                           institution_type, region_code, applicant_location,
                           nationality_code, passport_expires_at, arrival_at NULL
case_status_history: id, case_id, from_status NULL, to_status, reason_code,
                     changed_by_actor_id, changed_at
```

- [ ] **Step 1: Write failing Case relationship and constraint tests**

Test a valid transaction that creates `case` plus profile together. Reject:

- a `STUDENT_PASS` case committed without a profile;
- a profile whose programme belongs to another institution;
- a second profile for the same case;
- an unsupported service, application, institution, location, status, or stage value;
- duplicate `case_number`;
- `row_version < 1`.

```python
with pytest.raises(IntegrityError, match="Student Pass case requires exactly one profile"):
    session.add(valid_case_without_profile)
    session.commit()
```

- [ ] **Step 2: Run the Case tests and verify failure**

```bash
cd backend
TEST_DATABASE_URL=postgresql+psycopg://immigration_flow:immigration_flow_test@localhost:5433/immigration_flow_test uv run pytest tests/integration/test_case_schema.py -v
```

Expected: FAIL because revision 0002 and mappings do not exist.

- [ ] **Step 3: Implement Case and profile mappings**

Use `__tablename__ = "case"`; rely on SQLAlchemy identifier quoting for the reserved SQL word. Add a composite foreign key:

```python
ForeignKeyConstraint(
    ["programme_id", "institution_id"],
    ["programme.id", "programme.institution_id"],
    name="fk_student_pass_profile_programme_institution",
    ondelete="RESTRICT",
)
```

Use `CheckConstraint("row_version >= 1", name="row_version_positive")`. Add an index on `(status, stage)` and indexes for all foreign-key lookup columns.

- [ ] **Step 4: Add the deferred exact-profile constraint trigger**

Migration 0002 creates a `DEFERRABLE INITIALLY DEFERRED` constraint trigger on both `case` and `student_pass_case_profile`. Its PL/pgSQL function must:

```sql
SELECT service_type INTO service
FROM "case" WHERE id = case_id_to_check;

IF FOUND AND service = 'STUDENT_PASS'
   AND NOT EXISTS (
       SELECT 1 FROM student_pass_case_profile WHERE case_id = case_id_to_check
   ) THEN
    RAISE EXCEPTION 'Student Pass case requires exactly one profile';
END IF;

IF FOUND AND service <> 'STUDENT_PASS'
   AND EXISTS (
       SELECT 1 FROM student_pass_case_profile WHERE case_id = case_id_to_check
   ) THEN
    RAISE EXCEPTION 'profile is only valid for Student Pass cases';
END IF;
```

The function derives the affected ID from `NEW.id/OLD.id` for table `case`, and `NEW.case_id/OLD.case_id` for the profile table. Downgrade drops triggers, function, then tables.

- [ ] **Step 5: Apply 0002 and run Case tests**

```bash
cd backend
DATABASE_URL=postgresql+psycopg://immigration_flow:immigration_flow_test@localhost:5433/immigration_flow_test uv run alembic upgrade 0002_case_and_student_pass
TEST_DATABASE_URL=postgresql+psycopg://immigration_flow:immigration_flow_test@localhost:5433/immigration_flow_test uv run pytest tests/integration/test_case_schema.py -v
```

Expected: PASS, including direct-SQL tests proving the deferred trigger cannot be bypassed.

- [ ] **Step 6: Commit migration 0002**

```bash
git add backend/app backend/migrations/versions/0002_case_and_student_pass.py backend/tests/integration/test_case_schema.py
git commit -m "feat: add Case and Student Pass schema"
```

---

### Task 5: Migration 0003 — formal submissions and document versions

**Files:**
- Create: `backend/migrations/versions/0003_submissions_and_documents.py`
- Create: `backend/app/domains/submissions/__init__.py`
- Create: `backend/app/domains/submissions/models.py`
- Create: `backend/app/domains/documents/__init__.py`
- Create: `backend/app/domains/documents/models.py`
- Create: `backend/tests/integration/test_submission_document_schema.py`
- Modify: `backend/app/database/enums.py`
- Modify: `backend/app/database/models.py`

**Interfaces:**
- Consumes: `Actor` and `ImmigrationCase`
- Produces: `CaseSubmission`, `Document`, `DocumentVersion`, `SubmissionDocument`, `DocumentCheck`
- Produces revision `0003_submissions_and_documents` with down revision `0002_case_and_student_pass`

Persisted values:

```text
SubmissionType: INITIAL, SUPPLEMENTARY
SubmissionChannel: EMGS, IMMIGRATION_COUNTER, ONLINE_PORTAL, INSTITUTION_REPRESENTATIVE
DocumentStatus: DRAFT, ACTIVE, SUPERSEDED, VOID
DocumentCheckResult: PASS, FAIL, MANUAL_REVIEW
```

`DocumentType` contains:

```text
PHOTO, PASSPORT_BIODATA, PASSPORT_VISA_PAGES, PASSPORT_OBSERVATION_PAGES,
PASSPORT_ALL_PAGES, OFFER_LETTER, HEALTH_DECLARATION, ACADEMIC_RECORDS,
ENGLISH_EVIDENCE, LOE, NOC, PERSONAL_BOND, YELLOW_FEVER_CERTIFICATE,
IMMIGRATION_RECEIPT, OTHER
```

Exact fields follow the approved data dictionary. `submission_document` uses composite primary key `(submission_id, document_version_id, purpose)`.

- [ ] **Step 1: Write failing submission and document tests**

Cover valid drafts, versions, checks, and confirmed submissions. Reject:

- duplicate document version numbers;
- duplicate submission/document/purpose links;
- unknown persisted enum values;
- two confirmed initial submissions for one case;
- accepted submissions without reference and receipt evidence;
- confirmed submissions without `accepted_at`;
- a receipt document owned by another case.

```python
with pytest.raises(IntegrityError):
    session.add(CaseSubmission(
        case_id=case.id,
        submission_type=SubmissionType.INITIAL,
        channel=SubmissionChannel.EMGS,
        submitted_by_actor_id=actor.id,
        accepted_at=accepted_at,
        immigration_reference=None,
        receipt_document_version_id=None,
        confirmed_at=accepted_at,
    ))
    session.commit()
```

- [ ] **Step 2: Run the tests and verify failure**

```bash
cd backend
TEST_DATABASE_URL=postgresql+psycopg://immigration_flow:immigration_flow_test@localhost:5433/immigration_flow_test uv run pytest tests/integration/test_submission_document_schema.py -v
```

Expected: FAIL because revision 0003 and mappings do not exist.

- [ ] **Step 3: Implement the five mappings and exact constraints**

Create tables in this order to resolve the receipt relationship:

```text
document -> document_version -> case_submission -> submission_document -> document_check
```

Add the receipt foreign key after both target tables exist. Add these checks and index:

```sql
CHECK (
  accepted_at IS NULL OR (
    immigration_reference IS NOT NULL
    AND btrim(immigration_reference) <> ''
    AND receipt_document_version_id IS NOT NULL
  )
)

CHECK (confirmed_at IS NULL OR accepted_at IS NOT NULL)

CREATE UNIQUE INDEX uq_case_submission_confirmed_initial
ON case_submission (case_id)
WHERE submission_type = 'INITIAL' AND confirmed_at IS NOT NULL;
```

Store `details` as nullable `JSONB`. Enforce `size_bytes >= 0` and `version_number >= 1`.

- [ ] **Step 4: Add the deferred same-case receipt constraint**

Create a deferrable constraint trigger on `case_submission` that follows:

```sql
SELECT d.case_id INTO receipt_case_id
FROM document_version dv
JOIN document d ON d.id = dv.document_id
WHERE dv.id = NEW.receipt_document_version_id;

IF NEW.receipt_document_version_id IS NOT NULL
   AND (receipt_case_id IS NULL OR receipt_case_id <> NEW.case_id) THEN
    RAISE EXCEPTION 'receipt document version must belong to submission case';
END IF;
```

This trigger runs at transaction commit so a document version and submission may be created atomically.

- [ ] **Step 5: Apply 0003 and run tests**

```bash
cd backend
DATABASE_URL=postgresql+psycopg://immigration_flow:immigration_flow_test@localhost:5433/immigration_flow_test uv run alembic upgrade 0003_submissions_and_documents
TEST_DATABASE_URL=postgresql+psycopg://immigration_flow:immigration_flow_test@localhost:5433/immigration_flow_test uv run pytest tests/integration/test_submission_document_schema.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit migration 0003**

```bash
git add backend/app backend/migrations/versions/0003_submissions_and_documents.py backend/tests/integration/test_submission_document_schema.py
git commit -m "feat: add submission and document schema"
```

---

### Task 6: Migration 0004 — events, audit, and immutability

**Files:**
- Create: `backend/migrations/versions/0004_events_audit_and_immutability.py`
- Create: `backend/tests/integration/test_append_only_schema.py`
- Modify: `backend/app/domains/cases/models.py`
- Modify: `backend/app/database/models.py`

**Interfaces:**
- Consumes: Case, actor, submission, and document tables
- Produces: `CaseEvent`, `AuditEvent`
- Produces PostgreSQL function `prevent_append_only_mutation()`
- Produces PostgreSQL function `prevent_confirmed_initial_mutation()`
- Produces revision `0004_events_audit_and_immutability` with down revision `0003_submissions_and_documents`

Exact fields:

```text
case_event: id, case_id, event_type, event_payload JSONB, occurred_at,
            recorded_at, actor_id NULL
audit_event: id, case_id, actor_id NULL, action, entity_type, entity_id,
             before_summary JSONB NULL, after_summary JSONB NULL, occurred_at
```

- [ ] **Step 1: Write failing direct-SQL immutability tests**

Insert valid rows, then execute raw SQL updates and deletes. Each operation must raise `DBAPIError` for:

```text
document_version
document_check
case_status_history
case_event
audit_event
confirmed INITIAL case_submission
```

Also prove that an unconfirmed draft submission may still be updated, and that a `SUPPLEMENTARY` submission is not covered by the confirmed-initial trigger.

- [ ] **Step 2: Run the tests and verify mutation is currently possible**

```bash
cd backend
TEST_DATABASE_URL=postgresql+psycopg://immigration_flow:immigration_flow_test@localhost:5433/immigration_flow_test uv run pytest tests/integration/test_append_only_schema.py -v
```

Expected: FAIL because event tables and mutation-prevention triggers do not exist.

- [ ] **Step 3: Implement CaseEvent and AuditEvent mappings**

Use JSONB for payload/summaries, timezone-aware timestamps, restrictive foreign keys, and indexes on `(case_id, occurred_at)`. `actor_id` is nullable to preserve imported system events that do not yet map to an actor; new application-generated system events should use a `SYSTEM` actor.

- [ ] **Step 4: Create reusable append-only trigger function**

```sql
CREATE FUNCTION prevent_append_only_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION '% is append-only', TG_TABLE_NAME;
END;
$$;
```

Attach `BEFORE UPDATE OR DELETE` triggers to the five append-only tables. Use deterministic function and trigger names.

- [ ] **Step 5: Protect confirmed INITIAL submissions**

```sql
CREATE FUNCTION prevent_confirmed_initial_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.submission_type = 'INITIAL' AND OLD.confirmed_at IS NOT NULL THEN
    RAISE EXCEPTION 'confirmed initial submission is immutable';
  END IF;
  IF TG_OP = 'DELETE' THEN
    RETURN OLD;
  END IF;
  RETURN NEW;
END;
$$;
```

Attach it `BEFORE UPDATE OR DELETE` on `case_submission`. Downgrade removes every trigger before removing functions or tables.

- [ ] **Step 6: Apply 0004 and run all integration tests**

```bash
cd backend
DATABASE_URL=postgresql+psycopg://immigration_flow:immigration_flow_test@localhost:5433/immigration_flow_test uv run alembic upgrade head
TEST_DATABASE_URL=postgresql+psycopg://immigration_flow:immigration_flow_test@localhost:5433/immigration_flow_test uv run pytest tests/integration -v
```

Expected: PASS.

- [ ] **Step 7: Commit migration 0004**

```bash
git add backend/app backend/migrations/versions/0004_events_audit_and_immutability.py backend/tests/integration/test_append_only_schema.py
git commit -m "feat: add immutable event and audit history"
```

---

### Task 7: Migration round-trip and schema parity verification

**Files:**
- Create: `backend/tests/migration/test_migration_round_trip.py`
- Modify: `backend/tests/conftest.py`
- Modify: `backend/app/database/models.py` if parity test reveals missing imports only

**Interfaces:**
- Consumes: all four Alembic revisions and `Base.metadata`
- Produces: isolated helpers `alembic_upgrade(revision: str) -> None` and `alembic_downgrade(revision: str) -> None`
- Produces: automated proof of `base -> head -> base -> head`

- [ ] **Step 1: Write failing migration round-trip test**

```python
EXPECTED_TABLES = {
    "actor", "applicant_profile", "institution", "programme", "case",
    "student_pass_case_profile", "case_status_history", "case_submission",
    "document", "document_version", "submission_document", "document_check",
    "case_event", "audit_event",
}


def test_migrations_round_trip_and_restore_schema(test_database_url: str) -> None:
    alembic_downgrade("base")
    alembic_upgrade("head")
    assert expected_tables(test_database_url) == EXPECTED_TABLES | {"alembic_version"}
    assert_expected_functions_and_triggers(test_database_url)
    alembic_downgrade("base")
    assert expected_tables(test_database_url) == {"alembic_version"}
    alembic_upgrade("head")
    assert expected_tables(test_database_url) == EXPECTED_TABLES | {"alembic_version"}
```

- [ ] **Step 2: Run the migration test and capture the first mismatch**

```bash
cd backend
TEST_DATABASE_URL=postgresql+psycopg://immigration_flow:immigration_flow_test@localhost:5433/immigration_flow_test uv run pytest tests/migration/test_migration_round_trip.py -v
```

Expected: FAIL until the test helpers and exact schema assertions are implemented.

- [ ] **Step 3: Implement isolated Alembic helpers**

Build an Alembic `Config` pointing at `backend/alembic.ini`, inject the test URL, call `command.upgrade`/`command.downgrade`, and run `assert_test_database_url` before either command. Do not shell out from tests.

- [ ] **Step 4: Add exact schema, function, trigger, and metadata parity assertions**

Inspect PostgreSQL catalogs to assert deterministic names and attachment targets. Compare the mapped and migrated table/column sets; allow migration-only PostgreSQL functions and triggers, but no missing mapped table or column. Assert all four revision IDs and one linear head.

- [ ] **Step 5: Run round trip and full backend suite**

```bash
cd backend
TEST_DATABASE_URL=postgresql+psycopg://immigration_flow:immigration_flow_test@localhost:5433/immigration_flow_test uv run pytest -v
uv run ruff check app tests migrations
uv run ruff format --check app tests migrations
uv run mypy app
```

Expected: all commands PASS.

- [ ] **Step 6: Commit migration verification**

```bash
git add backend/tests backend/app/database/models.py
git commit -m "test: verify database migration round trip"
```

---

### Task 8: GitHub CI and reviewed dependency updates

**Files:**
- Create: `.github/workflows/backend-ci.yml`
- Create: `.github/dependabot.yml`

**Interfaces:**
- Consumes: `backend/uv.lock`, all backend tests, and existing Ruby validators
- Produces: required CI job `backend-and-knowledge-validation`
- Produces: weekly Dependabot update groups for `uv`, `docker`, and `github-actions`

- [ ] **Step 1: Add a local CI-equivalent command sequence and verify current behavior**

Run the exact intended checks locally before writing workflow YAML:

```bash
cd backend
uv sync --locked --all-groups
uv run ruff check app tests migrations
uv run ruff format --check app tests migrations
uv run mypy app
TEST_DATABASE_URL=postgresql+psycopg://immigration_flow:immigration_flow_test@localhost:5433/immigration_flow_test uv run pytest -v
cd ..
ruby scripts/validate_knowledge_base.rb
ruby tests/rules/student-pass-v1.policy_contract_test.rb
```

Expected: all commands PASS. If any fail, fix the task that owns the failure before adding CI.

- [ ] **Step 2: Create the GitHub Actions workflow**

Use read-only repository permissions, PostgreSQL 18.6 service credentials scoped to the job, and health checks. Pin setup-uv to its verified release commit and let Dependabot maintain it.

```yaml
name: Backend CI
on:
  pull_request:
  push:
    branches: [main]
permissions:
  contents: read
jobs:
  backend-and-knowledge-validation:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:18.6
        env:
          POSTGRES_DB: immigration_flow_test
          POSTGRES_USER: immigration_flow
          POSTGRES_PASSWORD: immigration_flow_test
        ports: ["5432:5432"]
        options: >-
          --health-cmd "pg_isready -U immigration_flow -d immigration_flow_test"
          --health-interval 5s --health-timeout 5s --health-retries 10
    env:
      DATABASE_URL: postgresql+psycopg://immigration_flow:immigration_flow_test@localhost:5432/immigration_flow_test
      TEST_DATABASE_URL: postgresql+psycopg://immigration_flow:immigration_flow_test@localhost:5432/immigration_flow_test
    steps:
      - uses: actions/checkout@v7
      - uses: astral-sh/setup-uv@c771a70e6277c0a99b617c7a806ffedaca235ff9 # v9.0.0
      - run: uv python install 3.14
      - run: uv sync --project backend --locked --all-groups
      - run: uv run --project backend ruff check backend/app backend/tests backend/migrations
      - run: uv run --project backend ruff format --check backend/app backend/tests backend/migrations
      - run: uv run --project backend mypy backend/app
      - run: uv run --project backend pytest backend/tests -v
      - run: ruby scripts/validate_knowledge_base.rb
      - run: ruby tests/rules/student-pass-v1.policy_contract_test.rb
```

- [ ] **Step 3: Configure weekly reviewed updates**

Create `.github/dependabot.yml` version 2 with:

```yaml
updates:
  - package-ecosystem: uv
    directory: /backend
    schedule: {interval: weekly}
    open-pull-requests-limit: 5
  - package-ecosystem: docker
    directory: /
    schedule: {interval: weekly}
    open-pull-requests-limit: 3
  - package-ecosystem: github-actions
    directory: /
    schedule: {interval: weekly}
    open-pull-requests-limit: 3
```

Do not configure automatic merging.

- [ ] **Step 4: Validate YAML and rerun the local CI sequence**

Use Ruby's built-in YAML parser:

```bash
ruby -e 'require "yaml"; YAML.load_file(".github/workflows/backend-ci.yml"); YAML.load_file(".github/dependabot.yml")'
```

Then rerun the commands from Step 1. Expected: PASS.

- [ ] **Step 5: Commit CI and update automation**

```bash
git add .github
git commit -m "ci: validate backend and dependency updates"
```

---

### Task 9: Developer documentation, security guardrails, and final verification

**Files:**
- Create: `backend/README.md`
- Modify: `README.md`
- Modify: `CONTRIBUTING.md`
- Modify: `.gitignore` only if final scan reveals a missing generated artifact

**Interfaces:**
- Consumes: completed Phase 2B.1 runtime and commands
- Produces: clean-machine setup instructions using only Docker Desktop and uv
- Produces: explicit statement that Phase 2B.1 has no Case business API and stores no real sensitive file bytes

- [ ] **Step 1: Write documentation acceptance checks**

Create a temporary checklist while editing and require the final docs to contain these literal commands:

```text
uv sync --project backend --locked --all-groups
docker compose up -d postgres
uv run --project backend alembic upgrade head
uv run --project backend uvicorn app.main:app --reload --app-dir backend
docker compose --profile test up -d postgres-test
uv run --project backend pytest backend/tests -v
docker compose stop
```

Also document copying `.env.example` to `.env`, the two health URLs, safe shutdown, and the separate destructive command for intentionally deleting the local volume.

- [ ] **Step 2: Update backend and project documentation**

`backend/README.md` explains setup, migrations, testing, health checks, and troubleshooting. Root `README.md` marks Phase 2B.1 implemented only after all verification passes, and identifies Phase 2B.2 as the next boundary. `CONTRIBUTING.md` requires migration tests, synthetic fixtures, no direct schema creation, and review of dependency PRs.

- [ ] **Step 3: Run secret and sensitive-data scans**

Run:

```bash
rg -n --hidden -g '!backend/uv.lock' -g '!.git/**' '(BEGIN (RSA|OPENSSH|EC) PRIVATE KEY|postgresql[^ ]+:[^ ]+@|passport_number|real applicant)' .
```

Expected: no private key, committed production connection URL, real passport number, or real applicant fixture. Demonstration local credentials in `.env.example`, Docker Compose, tests, and CI must be clearly scoped and non-production.

- [ ] **Step 4: Run complete Phase 2B.1 verification from a clean test database**

```bash
docker compose --profile test up -d postgres-test
cd backend
uv sync --locked --all-groups
TEST_DATABASE_URL=postgresql+psycopg://immigration_flow:immigration_flow_test@localhost:5433/immigration_flow_test uv run pytest -v
uv run ruff check app tests migrations
uv run ruff format --check app tests migrations
uv run mypy app
cd ..
ruby scripts/validate_knowledge_base.rb
ruby tests/rules/student-pass-v1.policy_contract_test.rb
```

Expected:

```text
All backend unit, integration, and migration tests pass.
Ruff check and format checks pass.
mypy passes in strict mode.
Knowledge base validates 13 sources, 17 requirements, 16 rules, and 12 cases.
Policy contract tests report 4 runs, 19 assertions, 0 failures, 0 errors.
```

- [ ] **Step 5: Verify development persistence without destroying data**

Start `postgres`, insert one synthetic marker row after migrations, run `docker compose restart postgres`, and confirm the marker remains. Remove the synthetic marker with a normal SQL transaction. Do not run `docker compose down -v` during this verification.

- [ ] **Step 6: Commit documentation and final status**

```bash
git add README.md CONTRIBUTING.md backend/README.md .gitignore
git commit -m "docs: document Phase 2B.1 database workflow"
```

- [ ] **Step 7: Verify remote GitHub state after publishing**

After pushing or browser-submitting all commits:

1. Confirm every changed GitHub file matches the verified local file.
2. Confirm the latest GitHub Actions run is green.
3. Confirm no unplanned application endpoint exists beyond `/health` and `/health/database`.
4. Confirm the public repository exposes no `.env`, test volume, secret, or real personal data.
5. Record the final commit SHA in the completion report.

---

## Execution checkpoints

- Checkpoint A — after Task 2: FastAPI and both health boundaries work; no schema tables exist yet.
- Checkpoint B — after Task 4: identity, institution, Case, and exact Student Pass profile constraints pass.
- Checkpoint C — after Task 6: all fourteen tables and database-level immutability protections pass.
- Checkpoint D — after Task 8: GitHub CI and reviewed dependency-update automation are active.
- Final checkpoint — after Task 9: clean migration round trip, full tests, knowledge regression, persistence, documentation, and remote verification all pass.

Do not begin Phase 2B.2 until the final checkpoint is complete and separately approved.
