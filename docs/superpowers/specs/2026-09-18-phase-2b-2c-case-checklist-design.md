# Phase 2B.2C — Case Rule Assignment and Checklist Design

**Status:** Approved by standing automatic-progression instruction  
**Date:** 2026-09-18  
**Scope:** Student Pass V1 assignment and requirement-checklist materialization.  

## Goal

Make an applicant-facing Student Pass case show the exact reviewed rule-set and
requirements that apply to its Immigration handover, while preserving the
historical version selected for that case.

## Boundary

This milestone adds an assignment and checklist only. It does not execute
deterministic eligibility rules, automatically approve or reject a case,
accept real document bytes, or implement policy-transition re-evaluation.
Those remain later milestones because they need their own immutable evaluation
and supersession model.

## Applicability policy

`case_submission.submitted_at` is the decisive timestamp. It records when the
applicant handed the completed package to Immigration. `accepted_at` is a later
receipt or acknowledgement and must not change the policy selection.

When a case is formally submitted, the service selects the one active Student
Pass rule-set version whose `IMMIGRATION_SUBMISSION_DATE` cutoff covers the
handover timestamp. A version applies when its cutoff is at or before
`submitted_at`; the newest qualifying active version wins. A missing applicable
version blocks submission with a clear conflict rather than silently selecting
a draft or review release.

## Data model

Migration `0008_case_rule_assignments_and_requirements` introduces:

- `case_rule_assignment`: immutable record of one rule-set version assigned to
  a case, its reason, assignment time, actor, and optional superseded assignment.
- `case_requirement`: materialized checklist item referring to the exact
  `requirement_version` from the assigned rule-set. Its status starts as
  `PENDING`; later milestones can link it to a document version.

`case.current_rule_set_version_id` becomes a query pointer to the currently
assigned release. `case_submission.applicable_rule_set_version_id` records the
initial submission's selected release. Both are set only within the same
transaction that writes the immutable assignment and checklist.

The migration protects assignment rows from update/delete and prevents duplicate
requirement versions for one case. The application creates a case event and an
audit event in the same transaction.

## Workflow

1. Applicant records document metadata while the case is `DRAFT`.
2. Applicant submits the case to Immigration.
3. The transaction resolves the applicable active Student Pass release using
   `submitted_at`, creates the initial assignment, materializes requirements
   linked by that release's `rule_requirement` provenance, writes checklist
   items, and then moves the case to `SUBMITTED`.
4. Applicant may retrieve `GET /api/v1/applicant/cases/{case_id}/checklist`.
   The response returns requirement code, statement, handling instructions,
   status, and the selected semantic release version. It never exposes source
   bodies, credentials, or unrelated cases.

## Security and failure handling

- Only the owner of the applicant profile can submit or read the checklist.
- Officers and other applicants receive `403`.
- A missing active release, missing rule provenance, or empty materialization
  prevents the submission transaction from committing.
- The service uses only approved, active rule-set versions; a release in
  `DRAFT`, `REVIEW`, or `RETIRED` is never eligible.
- The implementation stores synthetic metadata only and remains unsuitable for
  public production use without real authentication and secure object storage.

## Acceptance criteria

1. A case submitted at or after an active release cutoff receives that release,
   an immutable initial assignment, and a `PENDING` checklist.
2. The initial submission and the case pointer both reference the same release.
3. A case submitted before every active cutoff is rejected without partial rows.
4. A foreign applicant cannot read another applicant's checklist.
5. Assignment/checklist rows cannot be changed or deleted directly in SQL.
6. The exact requirement versions can be traced from checklist to assigned
   release through existing rule provenance.
7. New and existing regression tests, lint, formatting, type checks, and
   knowledge validation pass.
