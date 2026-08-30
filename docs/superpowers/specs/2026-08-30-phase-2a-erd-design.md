# Phase 2A — Student Pass V1 Data Model Design

**Status:** Approved in conversation; awaiting review of this written specification  
**Date:** 2026-08-30  
**Scope:** Logical data design only. PostgreSQL schemas, migrations, APIs, and application code belong to Phase 2B.

## 1. Goal

Define a durable relational model for the Student Pass V1 workflow that can:

- represent one applicant journey without hard-coding the whole platform to Student Pass;
- preserve the exact official sources, requirements, and rule versions used for every evaluation;
- choose and, when an explicit transition policy requires it, reassign rules from the date Immigration formally accepts an application, rather than from the date an officer processes it;
- retain immutable evidence and history while allowing current workflow state to be queried efficiently; and
- support later synchronization from the GitHub knowledge base into PostgreSQL.

The model is not an official Immigration system and does not make approval decisions.

## 2. Design decisions

### 2.1 Hybrid case model

Use a generic `case` record for shared workflow fields and a one-to-one `student_pass_case_profile` for Student Pass-specific facts. Future services can add their own profile tables without turning `case` into a wide collection of nullable columns.

### 2.2 Relational current state plus append-only history

Operational entities use normalized relational tables. `case_event`, `case_status_history`, and `audit_event` preserve history as append-only records. This is not full event sourcing: current case state remains directly queryable.

### 2.3 GitHub is the canonical knowledge authoring source

Official-source records, normalized requirements, and machine-readable rules continue to be reviewed in GitHub. PostgreSQL will later receive immutable synchronized versions. Every imported version retains its source Git commit so database state can be traced back to a reviewed repository change.

### 2.4 Rule applicability is based on accepted submission

An application is formally submitted only when all required forms and documents are handed to Immigration and Immigration issues an official receipt or reference. The timestamp is stored as `case_submission.accepted_at`.

- If `accepted_at` is before a policy's stated submission cutoff, the previous rule-set version applies.
- If `accepted_at` is on or after the cutoff, the new rule-set version applies.
- Later officer processing by itself does not change the selected rule-set version.
- Supplementary documents do not change the original selection.
- An attempted handover that Immigration rejects without issuing a receipt is not a formal submission.

The initial assignment is preserved in append-only history. When a newly activated official policy explicitly covers applications submitted on or after its cutoff, the system finds non-final cases whose `accepted_at` meets that condition, creates a superseding `case_rule_assignment`, and evaluates them using the new version. Cases submitted before the cutoff are not reassigned. Completed cases remain historical and are not automatically reopened.

If an official policy uses a different transition basis, it must be represented by a new explicit applicability policy rather than silently reusing this one.

### 2.5 Post-arrival medical deadline

Student Pass V1 uses a seven-calendar-day operational deadline from the recorded arrival time. The system creates reminders and an urgent follow-up when overdue. Missing the deadline must not automatically reject a case; an officer or institution follows up according to the official process.

This portfolio policy resolves the existing source-language discrepancy for V1. The Phase 1 requirement, rule message, and test description must be aligned during implementation.

## 3. System boundaries

### In scope

- Applicant, institution, programme, generic case, and Student Pass profile
- Formal and supplementary submissions
- Documents and immutable document versions
- Official sources, revisions, requirements, rules, and version links
- Rule evaluation results, findings, tasks, and deadlines
- Case status history, domain events, audit records, knowledge sync, and activation approval

### Deferred

- Full authentication, roles, permissions, sessions, and identity-provider integration
- Physical database types, indexes, migrations, partitioning, and retention jobs
- Rule execution code, website monitoring, and automated synchronization
- Other immigration-service profile tables
- Production storage of real passports or personal data

`actor` is therefore a minimal interface representing an applicant, institution worker, officer, administrator, or system process. Full RBAC is a later security design.

## 4. Data architecture

The model is divided into six areas:

1. **Identity and reference:** `actor`, `applicant_profile`, `institution`, `programme`
2. **Case:** `case`, `student_pass_case_profile`, `case_status_history`
3. **Submission and document:** `case_submission`, `document`, `document_version`, `submission_document`, `document_check`
4. **Official knowledge:** `knowledge_source`, `source_revision`, `requirement`, `requirement_version`, `requirement_source`, `rule_set`, `rule_set_version`, `rule_definition`, `rule_version`, `rule_requirement`
5. **Evaluation and work:** `case_rule_assignment`, `case_requirement`, `rule_evaluation`, `evaluation_finding`, `case_task`, `case_deadline`
6. **History and governance:** `case_event`, `audit_event`, `knowledge_sync_run`, `approval_event`

The detailed diagram is in `docs/architecture/STUDENT_PASS_V1_ERD.md`; field definitions and invariants are in `docs/architecture/STUDENT_PASS_V1_DATA_DICTIONARY.md`.

## 5. Core flows

### 5.1 Draft case

1. Create an applicant profile and case.
2. Create the one-to-one Student Pass profile.
3. Resolve the current preparation rule set for checklist guidance, but do not lock final applicability yet.
4. Record status changes and significant events.

### 5.2 Formal submission

1. Institution or applicant records the Immigration receipt/reference and `accepted_at`.
2. System selects the currently approved rule-set version whose transition policy covers that timestamp.
3. System writes the initial version to `case_submission.applicable_rule_set_version_id`, creates a `case_rule_assignment`, and updates `case.current_rule_set_version_id` as a queryable pointer to that assignment.
4. The confirmed initial submission becomes immutable.
5. A rule evaluation runs from an immutable fact snapshot.

At most one confirmed `INITIAL` submission exists per case.

### 5.3 Supplementary submission

1. Add a `SUPPLEMENTARY` submission linked to exact document versions.
2. Preserve the original applicable rule-set version.
3. Re-evaluate the case using its current rule assignment and a new input snapshot.
4. Supersede the prior evaluation without deleting it.

### 5.4 Official rule update

1. Detect or manually register a changed official source.
2. Create a new immutable source revision, requirement versions, and rule versions in GitHub.
3. Synchronize them as a draft rule-set version with its Git commit.
4. Review and approve the version.
5. Activate it with official publication, effective, and submission-cutoff timestamps.
6. Assign it to future formal submissions covered by its transition policy.
7. Find non-final cases already accepted on or after the cutoff that still reference an older version.
8. Create a superseding rule assignment and new evaluation for each affected case; never overwrite the previous assignment or evaluation.

Existing cases submitted before the cutoff keep their assigned version, even if still being processed. Non-final cases submitted on or after the cutoff use the new version and are evaluated accordingly. Completed cases are not automatically reopened.

### 5.5 Post-arrival medical tracking

1. Record `arrival_at` in Malaysia time.
2. Create `POST_ARRIVAL_MEDICAL` deadline with `due_at = arrival_at + 7 calendar days`.
3. Mark it complete when screening evidence is recorded.
4. If overdue, create a reminder/urgent task and retain the case for human handling; do not create an automatic rejection outcome.

## 6. Integrity and immutability rules

- Internal primary keys are UUIDs; business identifiers such as `case_number` are separately unique.
- Stored timestamps are UTC; official cutoff interpretation uses `Asia/Kuala_Lumpur` unless the policy explicitly specifies otherwise.
- Confirmed initial submission records, receipt document versions, and rule assignments are immutable.
- Document versions, source revisions, requirement versions, rule versions, evaluations, status history, case events, and audit events are append-only.
- Active rule-set versions are immutable and cannot have overlapping applicability windows for the same rule set and transition basis.
- A rule evaluation must reference the exact rule-set version and an immutable input snapshot.
- Every material requirement version must link to at least one source revision.
- Every rule version must link to its supporting requirement version or versions.
- Supplementary submissions cannot create or change rule applicability. Only an approved transition policy can create a superseding rule assignment.
- Optimistic concurrency uses `case.row_version` to prevent silent overwrites.

## 7. Failure handling

- **No official receipt:** keep the case in preparation; do not create a confirmed initial submission.
- **Ambiguous or missing cutoff:** block activation and require a human approval record.
- **Overlapping rule windows:** reject the knowledge activation operation.
- **Knowledge sync failure:** keep the previous active database version, record the failed sync, and never partially activate a new rule set.
- **Missing source provenance:** reject requirement/rule activation.
- **Stale write:** reject the update using `row_version`; the caller reloads current case state.
- **Evaluation failure:** preserve the previous evaluation, record the error event, and create a review task if the case cannot proceed safely.
- **Medical deadline overdue:** notify and escalate; never translate lateness directly into rejection.

## 8. Acceptance scenarios

1. A case accepted one minute before the official cutoff retains the old rule-set version while processing continues after the effective date.
2. A case accepted exactly at the cutoff uses the new rule-set version.
3. A rejected handover without a receipt does not lock any rule-set version.
4. A supplementary document submitted after the cutoff does not move an older case to the new rule set.
5. When a new policy activates, a non-final case accepted on or after its cutoff receives a superseding rule assignment and automatic re-evaluation.
6. A non-final case accepted before that cutoff keeps its previous assignment.
7. A completed case is not automatically reopened by activation.
8. Two evaluations of one case retain both input snapshots and clearly identify which one supersedes the other.
9. A new official revision can be traced through requirement and rule versions to the Git commit that introduced it.
10. Activation fails when rule applicability windows overlap.
11. A student without completed medical screening receives a due reminder within seven calendar days.
12. On day eight, the case receives urgent follow-up/manual handling but no automatic rejection result.
13. A concurrent update using an old `row_version` is rejected without losing the newer data.

## 9. Phase 2A deliverables

- This approved design specification
- Logical Mermaid ERD
- Logical data dictionary and invariants
- ADR 0001: hybrid generic-case model
- ADR 0002: versioned knowledge activation
- ADR 0003: submission-date rule applicability

After the user reviews these written artifacts, the next step is a separate implementation plan. PostgreSQL enters only when that plan is approved.
