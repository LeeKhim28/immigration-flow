# Phase 2B.2B Applicant/Officer Vertical Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a testable Student Pass journey from applicant draft to formal Immigration handover and officer processing.

**Architecture:** Keep HTTP concerns in a focused `app/api` package and workflow/authorization/transaction logic in `app/domains/cases/service.py`. The API uses a synthetic `X-Actor-Id` header that resolves an existing `Actor`; all current-state updates and append-only history records are committed together through the existing SQLAlchemy session dependency.

**Tech Stack:** Python 3.14, FastAPI, Pydantic 2, SQLAlchemy 2, PostgreSQL, Alembic, pytest, Ruff, mypy.

**Spec:** `docs/superpowers/specs/2026-09-18-phase-2b-2b-applicant-officer-vertical-slice-design.md`

## Global Constraints

- V1 supports only `STUDENT_PASS`, `NEW`, and `OUTSIDE_MALAYSIA` for this flow.
- Requests use `X-Actor-Id` only for synthetic portfolio actors; it is not production authentication.
- No endpoint may claim, calculate, or record automated Immigration approval or rejection.
- Applicant submission records non-null `submitted_at` and represents completed handover, not proof of an official receipt or decision.
- Every material workflow transition writes `case_status_history`, `case_event`, and `audit_event` in the same transaction.
- Preserve existing database constraints, migrations, knowledge governance behavior, and test isolation.

---

## File structure

| File | Responsibility |
|---|---|
| `backend/app/api/dependencies.py` | Parse and resolve the synthetic actor header. |
| `backend/app/api/schemas.py` | Pydantic request and response contracts. |
| `backend/app/api/applicant.py` | Applicant draft and submission routes. |
| `backend/app/api/officer.py` | Officer queue and processing routes. |
| `backend/app/domains/cases/service.py` | Ownership checks, state transitions, and append-only evidence. |
| `backend/migrations/versions/0007_submission_handover_timestamp.py` | Add the distinct applicant handover timestamp. |
| `backend/app/main.py` | Register the versioned API router. |
| `backend/tests/integration/test_case_api.py` | Real PostgreSQL API acceptance tests. |
| `backend/README.md` | Synthetic demo seeding and endpoint examples. |

## Task 1: Preserve applicant handover time separately from acceptance

**Files:**

- Modify: `backend/app/domains/submissions/models.py`
- Create: `backend/migrations/versions/0007_submission_handover_timestamp.py`
- Modify: `backend/tests/migration/test_migration_round_trip.py`
- Test: `backend/tests/integration/test_submission_document_schema.py`

**Interfaces:**

- Produces `CaseSubmission.submitted_at: datetime`, non-null and stored in UTC.
- Preserves optional `accepted_at` as an acceptance-with-evidence timestamp.

- [ ] **Step 1: Write the failing persistence test**

```python
def test_submission_records_handover_time_without_official_acceptance(session: Session) -> None:
    case, applicant = _persist_case(session, "HANDOVER")
    submission = _submission(
        case,
        applicant,
        submitted_at=datetime(2026, 9, 18, 10, 0, tzinfo=UTC),
    )
    session.add(submission)
    session.commit()
    assert submission.submitted_at == datetime(2026, 9, 18, 10, 0, tzinfo=UTC)
    assert submission.accepted_at is None
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --project backend pytest backend/tests/integration/test_submission_document_schema.py::test_submission_records_handover_time_without_official_acceptance -q`

Expected: FAIL because `submitted_at` does not exist.

- [ ] **Step 3: Implement the forward-only migration and mapped field**

```python
op.add_column(
    "case_submission",
    sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
)
op.execute("UPDATE case_submission SET submitted_at = COALESCE(accepted_at, now())")
op.alter_column("case_submission", "submitted_at", nullable=False)
```

Add `submitted_at` to `CaseSubmission`; update the migration head expectation.

- [ ] **Step 4: Run focused migration and persistence tests**

Run: `uv run --project backend pytest backend/tests/integration/test_submission_document_schema.py::test_submission_records_handover_time_without_official_acceptance backend/tests/migration/test_migration_round_trip.py -q`

Expected: PASS.

## Task 2: Actor dependency and draft-case workflow

**Files:**

- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/dependencies.py`
- Create: `backend/app/api/schemas.py`
- Create: `backend/app/api/applicant.py`
- Create: `backend/app/domains/cases/service.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/integration/test_case_api.py`

**Interfaces:**

- Produces `get_current_actor(session, x_actor_id) -> Actor`.
- Produces `create_student_pass_draft(session, actor, command) -> ImmigrationCase`.
- Produces `POST /api/v1/applicant/cases` returning `201`.

- [ ] **Step 1: Write the failing API test**

```python
def test_applicant_creates_student_pass_draft(client: TestClient, session: Session) -> None:
    applicant, profile, institution, programme = seed_applicant_context(session)
    response = client.post(
        "/api/v1/applicant/cases",
        headers={"X-Actor-Id": str(applicant.id)},
        json=draft_payload(profile.id, institution.id, programme.id),
    )
    assert response.status_code == 201
    assert response.json()["status"] == "DRAFT"
    assert count_rows(session, "student_pass_case_profile") == 1
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --project backend pytest backend/tests/integration/test_case_api.py::test_applicant_creates_student_pass_draft -q`

Expected: FAIL because the route does not exist.

- [ ] **Step 3: Implement the minimal draft path**

```python
def create_student_pass_draft(session: Session, actor: Actor, command: DraftCaseCommand) -> ImmigrationCase:
    profile = session.get(ApplicantProfile, command.applicant_profile_id)
    _require_profile_owner(profile, actor)
    case = ImmigrationCase(...status=CaseStatus.DRAFT, stage=CaseStage.PRE_SUBMISSION)
    session.add(case)
    session.flush()
    session.add(StudentPassCaseProfile(case_id=case.id, ...))
    _record_transition(session, case, None, CaseStatus.DRAFT, "CASE_CREATED", actor)
    session.commit()
    return case
```

- [ ] **Step 4: Run the focused test to verify it passes**

Run: `uv run --project backend pytest backend/tests/integration/test_case_api.py::test_applicant_creates_student_pass_draft -q`

Expected: PASS.

- [ ] **Step 5: Add and verify ownership rejection**

```python
def test_applicant_cannot_create_case_for_another_profile(client: TestClient, session: Session) -> None:
    applicant, _profile, institution, programme = seed_applicant_context(session)
    _other, other_profile, _other_institution, _other_programme = seed_applicant_context(session)
    response = client.post(...headers={"X-Actor-Id": str(applicant.id)}, json=draft_payload(other_profile.id, institution.id, programme.id))
    assert response.status_code == 403
```

Run: `uv run --project backend pytest backend/tests/integration/test_case_api.py -q`

Expected: PASS.

## Task 3: Applicant formal handover

**Files:**

- Modify: `backend/app/api/schemas.py`
- Modify: `backend/app/api/applicant.py`
- Modify: `backend/app/domains/cases/service.py`
- Test: `backend/tests/integration/test_case_api.py`

**Interfaces:**

- Consumes `POST /api/v1/applicant/cases/{case_id}/submit` body `{"channel": "ONLINE_PORTAL"}`.
- Produces `submit_case_to_immigration(session, actor, case_id, channel) -> CaseSubmission`.

- [ ] **Step 1: Write the failing submission test**

```python
def test_applicant_submission_records_handover_and_moves_case_to_submitted(client: TestClient, session: Session) -> None:
    applicant, case = seed_draft_case(session)
    response = client.post(f"/api/v1/applicant/cases/{case.id}/submit", headers={"X-Actor-Id": str(applicant.id)}, json={"channel": "ONLINE_PORTAL"})
    assert response.status_code == 201
    assert response.json()["status"] == "SUBMITTED"
    assert submission_for_case(session, case.id).submission_type is SubmissionType.INITIAL
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --project backend pytest backend/tests/integration/test_case_api.py::test_applicant_submission_records_handover_and_moves_case_to_submitted -q`

Expected: FAIL because the submission route does not exist.

- [ ] **Step 3: Implement one transactional handover**

```python
def submit_case_to_immigration(session: Session, actor: Actor, case_id: UUID, channel: SubmissionChannel) -> CaseSubmission:
    case = _owned_case(session, case_id, actor)
    _require_status(case, CaseStatus.DRAFT)
    submission = CaseSubmission(case_id=case.id, submission_type=SubmissionType.INITIAL, channel=channel, submitted_by_actor_id=actor.id, submitted_at=utc_now())
    session.add(submission)
    _transition(session, case, CaseStatus.SUBMITTED, CaseStage.PRE_SUBMISSION, "APPLICANT_SUBMITTED", actor)
    session.commit()
    return submission
```

- [ ] **Step 4: Run the focused test to verify it passes**

Run: `uv run --project backend pytest backend/tests/integration/test_case_api.py::test_applicant_submission_records_handover_and_moves_case_to_submitted -q`

Expected: PASS.

- [ ] **Step 5: Add repeated-submit regression test**

```python
def test_repeated_submission_returns_conflict_without_a_second_initial_record(client: TestClient, session: Session) -> None:
    applicant, case = seed_draft_case(session)
    submit_case(client, applicant, case)
    response = submit_case(client, applicant, case)
    assert response.status_code == 409
    assert count_initial_submissions(session, case.id) == 1
```

Run: `uv run --project backend pytest backend/tests/integration/test_case_api.py -q`

Expected: PASS.

## Task 4: Officer queue and processing transition

**Files:**

- Create: `backend/app/api/officer.py`
- Modify: `backend/app/api/schemas.py`
- Modify: `backend/app/domains/cases/service.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/integration/test_case_api.py`

**Interfaces:**

- Produces `GET /api/v1/officer/cases?status=SUBMITTED`.
- Produces `start_case_processing(session, officer, case_id) -> ImmigrationCase`.
- Produces `POST /api/v1/officer/cases/{case_id}/start-processing`.

- [ ] **Step 1: Write the failing officer queue test**

```python
def test_officer_lists_submitted_cases(client: TestClient, session: Session) -> None:
    officer = seed_officer(session)
    _applicant, case = seed_submitted_case(session)
    response = client.get("/api/v1/officer/cases", headers={"X-Actor-Id": str(officer.id)})
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [str(case.id)]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --project backend pytest backend/tests/integration/test_case_api.py::test_officer_lists_submitted_cases -q`

Expected: FAIL because the officer route does not exist.

- [ ] **Step 3: Implement the queue and actor-type check**

```python
def list_officer_cases(session: Session, status: CaseStatus) -> list[ImmigrationCase]:
    return list(session.scalars(select(ImmigrationCase).where(ImmigrationCase.status == status).order_by(ImmigrationCase.created_at)))
```

- [ ] **Step 4: Write and run the failing processing test**

```python
def test_officer_starts_processing_and_records_evidence(client: TestClient, session: Session) -> None:
    officer = seed_officer(session)
    _applicant, case = seed_submitted_case(session)
    response = client.post(f"/api/v1/officer/cases/{case.id}/start-processing", headers={"X-Actor-Id": str(officer.id)})
    assert response.status_code == 200
    assert response.json()["status"] == "IN_PROCESS"
    assert evidence_actions(session, case.id) == {"CASE_STATUS_CHANGED", "CASE_PROCESSING_STARTED"}
```

Run: `uv run --project backend pytest backend/tests/integration/test_case_api.py::test_officer_starts_processing_and_records_evidence -q`

Expected: FAIL because the processing route does not exist.

- [ ] **Step 5: Implement the processing transition and run focused tests**

```python
def start_case_processing(session: Session, officer: Actor, case_id: UUID) -> ImmigrationCase:
    case = _require_case(session, case_id)
    _require_status(case, CaseStatus.SUBMITTED)
    case.assigned_to_actor_id = officer.id
    _transition(session, case, CaseStatus.IN_PROCESS, CaseStage.IMMIGRATION_PROCESSING, "OFFICER_STARTED_PROCESSING", officer)
    session.commit()
    return case
```

Run: `uv run --project backend pytest backend/tests/integration/test_case_api.py -q`

Expected: PASS.

## Task 5: Error behavior, documentation, and complete verification

**Files:**

- Modify: `backend/tests/integration/test_case_api.py`
- Modify: `backend/README.md`

**Interfaces:**

- Confirms API responses use only the documented `401`, `403`, `404`, `409`, and `422` semantics.
- Documents synthetic setup and the four API calls without exposing a production workflow.

- [ ] **Step 1: Add failing authorization and state-conflict tests**

```python
def test_wrong_actor_type_cannot_access_officer_queue(client: TestClient, session: Session) -> None:
    applicant, _case = seed_submitted_case(session)
    response = client.get("/api/v1/officer/cases", headers={"X-Actor-Id": str(applicant.id)})
    assert response.status_code == 403

def test_officer_cannot_start_processing_twice(client: TestClient, session: Session) -> None:
    officer = seed_officer(session)
    _applicant, case = seed_submitted_case(session)
    start_processing(client, officer, case)
    response = start_processing(client, officer, case)
    assert response.status_code == 409
```

- [ ] **Step 2: Run the error tests to verify they fail**

Run: `uv run --project backend pytest backend/tests/integration/test_case_api.py -q`

Expected: FAIL until role checks and state conflict handling are complete.

- [ ] **Step 3: Implement minimal safe error translation and documentation**

```python
raise HTTPException(status_code=403, detail="actor is not permitted for this action")
raise HTTPException(status_code=409, detail="case is not in the required state")
```

Document `X-Actor-Id` as synthetic-only and include `curl` examples using placeholder UUIDs.

- [ ] **Step 4: Run all project verification commands**

Run: `uv run --project backend pytest backend/tests -q`

Run: `uv run --project backend ruff check backend`

Run: `uv run --project backend ruff format --check backend`

Run: `uv run --project backend mypy backend/app`

Run: `ruby scripts/validate_knowledge_base.rb`

Expected: all commands exit 0.

- [ ] **Step 5: Review the diff and prepare the branch for a commit**

Run: `git diff --check && git status --short --branch`

Expected: no whitespace errors and a concise list of Phase 2B.2A/2B.2B changes ready for the user’s normal commit/PR process.
