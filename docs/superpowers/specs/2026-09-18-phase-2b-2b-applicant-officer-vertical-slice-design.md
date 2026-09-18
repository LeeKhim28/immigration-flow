# Phase 2B.2B Applicant/Officer Vertical Slice Design

## Status

Approved for implementation as the next portfolio milestone.

## Goal

Provide a small, end-to-end Student Pass workflow that demonstrates how a synthetic applicant creates a case, formally hands it to Immigration, and how a synthetic officer receives and starts processing that case.

This milestone is a portfolio demo boundary, not a government integration and not an approval engine.

## Scope

### Included

1. Applicant creates a Student Pass draft case and its required Student Pass profile in one transaction.
2. Applicant submits the case through a formal handover endpoint. The handover records the channel and a distinct `submitted_at` timestamp, creates an initial `case_submission`, and moves the case to `SUBMITTED`.
3. Officer lists submitted cases and starts processing one case, moving it to `IN_PROCESS`.
4. Every material transition writes status history, a case event, and an audit event.
5. Pydantic request/response contracts and integration tests exercise the API against the test PostgreSQL database.

### Explicitly excluded

- Real authentication, identity verification, or government/EMGS integration.
- Binary file upload or storage. Document records remain a later milestone.
- Automatic eligibility, approval, rejection, or legal advice.
- Rule evaluation during submission. Rule assignment and re-evaluation remain governed by the knowledge activation milestone.
- Applicant and officer frontend applications.
- Additional immigration service types.

## Demo actor boundary

For the portfolio demo, each request supplies `X-Actor-Id`. The API loads that actor from the database and enforces the actor type. This is intentionally explicit and temporary; production authentication is a separate security milestone and must replace this header before public deployment.

Required actor types:

- Applicant endpoints: `APPLICANT` only, and the actor must own the referenced applicant profile.
- Officer endpoints: `OFFICER` only.

Missing, unknown, or wrong-type actors return `401` or `403` without leaking database details.

## API contract

### Create draft

`POST /api/v1/applicant/cases`

Request body:

```json
{
  "case_number": "CASE-2026-0001",
  "applicant_profile_id": "uuid",
  "application_type": "NEW",
  "institution_id": "uuid",
  "programme_id": "uuid",
  "institution_type": "IPTS",
  "region_code": "MY-10",
  "applicant_location": "OUTSIDE_MALAYSIA",
  "nationality_code": "CN",
  "passport_expires_at": "2030-01-01T00:00:00Z"
}
```

The actor in `X-Actor-Id` must own `applicant_profile_id`. The service creates `case` with `STUDENT_PASS`, `DRAFT`, and `PRE_SUBMISSION`, then creates exactly one `student_pass_case_profile`. The transaction commits only if both rows satisfy all database constraints.

Response: `201` with the case identifier, case number, status, stage, and profile identifier.

### Submit to Immigration

`POST /api/v1/applicant/cases/{case_id}/submit`

Request body:

```json
{
  "channel": "ONLINE_PORTAL"
}
```

The actor must own the case. The case must be `DRAFT` and have its Student Pass profile. The service creates one `INITIAL` submission with `submitted_by_actor_id` and `submitted_at` set to the server timestamp, then moves the case to `SUBMITTED`. `accepted_at`, `immigration_reference`, and receipt evidence stay empty: they represent a later Immigration acceptance event, not the applicant’s handover. In this demo, the server-created submission record represents the applicant’s completed handover to Immigration; it does not claim that an official receipt or approval exists.

The endpoint is idempotency-safe at the workflow level: a second call for a non-draft case returns `409` and does not create another initial submission.

### Officer queue

`GET /api/v1/officer/cases?status=SUBMITTED`

The actor must be an officer. The response contains synthetic case summaries ordered by `created_at` ascending. The default status is `SUBMITTED`; only `SUBMITTED` and `IN_PROCESS` are accepted as filters in this milestone.

### Start processing

`POST /api/v1/officer/cases/{case_id}/start-processing`

The actor must be an officer. The case must be `SUBMITTED`. The service assigns the case to that officer and moves it to `IN_PROCESS`, writing the same history/event/audit records as other transitions. Repeating the action returns `409`.

## State and history rules

Only these transitions are implemented:

```text
DRAFT --applicant_submit--> SUBMITTED
SUBMITTED --officer_start_processing--> IN_PROCESS
```

The current case row is mutable for the active state and assignment. `CaseStatusHistory`, `CaseEvent`, and `AuditEvent` are append-only evidence of each transition. All state mutation and evidence writes occur in one database transaction.

`case_submission.submitted_at` is a non-null timestamp added through a forward-only Alembic migration. It records the applicant’s handover separately from optional later `accepted_at`; this preserves the established rule that policy applicability is based on Immigration submission date rather than officer processing date.

## Error contract

- `400`: malformed request or unsupported enum value.
- `401`: missing or unknown `X-Actor-Id`.
- `403`: actor type or ownership violation.
- `404`: case/profile/institution/programme not found.
- `409`: duplicate case number, invalid current state, or repeated submission/processing action.
- `422`: Pydantic validation error.

Errors use a stable `{ "detail": "..." }` shape and never include SQL statements, connection strings, or stack traces.

## Testing strategy

Integration tests use the existing migration-backed PostgreSQL fixtures and real FastAPI `TestClient` requests. The minimum acceptance set is:

1. Applicant can create a valid draft and profile atomically.
2. Applicant cannot create a case for another applicant profile.
3. Submit creates one initial submission and moves the case to `SUBMITTED`.
4. A repeated submission is rejected without a second submission row.
5. An officer can list the submitted queue.
6. An applicant cannot use officer endpoints and an officer cannot submit an applicant case.
7. Officer start-processing assigns the case and records all three history records.
8. Invalid state transitions return `409` and leave the case unchanged.

Existing schema, knowledge governance, migration, lint, type, and repository validation suites remain mandatory.

## Success criteria

- A reviewer can seed synthetic actors/reference data and run the complete Applicant → Immigration handover → Officer processing path through documented API calls.
- All new behavior is covered by tests that were observed failing before implementation.
- No endpoint claims or computes official approval.
- The API can be disabled or replaced without changing the underlying case and audit model.
