# Case Rule Assignment and Checklist Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Assign the applicable active Student Pass rule-set at applicant handover and expose its materialized, source-traceable checklist to the case owner.

**Architecture:** Add immutable assignment and checklist tables, then extend the existing submission transaction to select an active release using `submitted_at`. Checklist items are built from the existing `rule_requirement` provenance links. An applicant-only read route exposes the immutable assignment and current checklist state.

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL 18, pytest, Ruff, mypy.

**Spec:** `docs/superpowers/specs/2026-09-18-phase-2b-2c-case-checklist-design.md`

## Global Constraints

- `submitted_at`, not `accepted_at`, controls Student Pass V1 applicability.
- Only `ACTIVE` rule-set versions are selectable.
- Assignment and versioned checklist history is append-only.
- The system is preparation/triage only and must not make an official immigration decision.
- Store only synthetic metadata; do not accept real document bytes or credentials.

---

### Task 1: Add immutable assignment and checklist persistence

**Files:**
- Create: `backend/migrations/versions/0008_case_rule_assignments_and_requirements.py`
- Modify: `backend/app/domains/cases/models.py`
- Modify: `backend/app/domains/knowledge/models.py`
- Modify: `backend/app/database/models.py`
- Test: `backend/tests/integration/test_case_rule_assignment_schema.py`

**Interfaces:**
- Consumes: `RuleSetVersion`, `RuleRequirement`, `RequirementVersion`, and `ImmigrationCase`.
- Produces: `CaseRuleAssignment` and `CaseRequirement` ORM models.

- [ ] **Step 1: Write failing schema tests**

```python
def test_assignment_and_checklist_are_immutable(session: Session) -> None:
    assignment, requirement = seed_assignment_with_requirement(session)
    with pytest.raises(ProgrammingError, match="immutable"):
        session.execute(text("DELETE FROM case_rule_assignment WHERE id = :id"), {"id": assignment.id})
        session.commit()
```

- [ ] **Step 2: Run the schema test to verify it fails**

Run: `uv run --project backend pytest backend/tests/integration/test_case_rule_assignment_schema.py -q`

Expected: failure because the migration and models do not exist.

- [ ] **Step 3: Implement migration and model mappings**

Create UUID-keyed tables with foreign keys to case, rule-set version, requirement version, and document version. Add unique `(case_id, requirement_version_id)` and immutable update/delete triggers. Add nullable current/applicable release pointers only with restricted foreign keys.

- [ ] **Step 4: Run schema tests to verify they pass**

Run: `uv run --project backend pytest backend/tests/integration/test_case_rule_assignment_schema.py -q`

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app backend/migrations backend/tests/integration/test_case_rule_assignment_schema.py
git commit -m "feat: persist case rule assignments"
```

### Task 2: Assign a release and materialize requirements during handover

**Files:**
- Modify: `backend/app/domains/cases/service.py`
- Modify: `backend/tests/integration/test_case_api.py`
- Test: `backend/tests/unit/cases/test_rule_assignment.py`

**Interfaces:**
- Consumes: `submit_case_to_immigration(session, actor, case_id, channel)`.
- Produces: a submitted case with linked initial submission, `CaseRuleAssignment`, and `CaseRequirement` rows.

- [ ] **Step 1: Write failing tests**

```python
def test_submission_assigns_newest_active_release_and_materializes_checklist():
    response = client.post(submission_url, headers=owner_header, json={"channel": "ONLINE_PORTAL"})
    assert response.status_code == 201
    assert submission.applicable_rule_set_version_id == active_release.id
    assert case.current_rule_set_version_id == active_release.id
    assert checklist_statuses == ["PENDING"]
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `uv run --project backend pytest backend/tests/integration/test_case_api.py -q`

Expected: failure because submission does not yet assign a release.

- [ ] **Step 3: Implement the atomic assignment service**

Select the newest active Student Pass release with cutoff no later than the UTC handover instant. Validate rule provenance, create assignment/checklist/event/audit rows, set the two release pointers, and commit only after all writes are valid. Return a conflict with no writes if no release applies.

- [ ] **Step 4: Run focused and schema tests**

Run: `uv run --project backend pytest backend/tests/integration/test_case_api.py backend/tests/integration/test_case_rule_assignment_schema.py -q`

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/domains/cases/service.py backend/tests
git commit -m "feat: assign rules at applicant handover"
```

### Task 3: Expose the owned applicant checklist

**Files:**
- Modify: `backend/app/api/applicant.py`
- Modify: `backend/app/api/schemas.py`
- Test: `backend/tests/integration/test_case_api.py`
- Modify: `backend/README.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: `GET /api/v1/applicant/cases/{case_id}/checklist` with `X-Actor-Id`.
- Produces: selected semantic version and checklist entries for the case owner.

- [ ] **Step 1: Write failing ownership and response tests**

```python
def test_case_owner_reads_materialized_checklist(client: TestClient) -> None:
    response = client.get(checklist_url, headers=owner_header)
    assert response.status_code == 200
    assert response.json()["requirements"][0]["status"] == "PENDING"

def test_other_applicant_cannot_read_case_checklist(client: TestClient) -> None:
    assert client.get(checklist_url, headers=other_header).status_code == 403
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `uv run --project backend pytest backend/tests/integration/test_case_api.py -q`

Expected: failure because the checklist route does not exist.

- [ ] **Step 3: Implement the read route and document the demo boundary**

Return only requirement code, statement, machine-handling instruction, current status, and assigned semantic version. Enforce applicant ownership before querying checklist rows. Document that the route displays metadata/checklist state, not a real-file upload or official decision.

- [ ] **Step 4: Run final verification**

Run: `uv run --project backend pytest backend/tests -q && uv run --project backend ruff check backend && uv run --project backend ruff format --check backend && uv run --project backend mypy backend/app && ruby scripts/validate_knowledge_base.rb && git diff --check`

Expected: all commands succeed; only the known upstream TestClient deprecation warning may remain.

- [ ] **Step 5: Commit**

```bash
git add README.md backend/README.md backend/app/api backend/tests/integration/test_case_api.py
git commit -m "feat: expose applicant requirement checklist"
```
