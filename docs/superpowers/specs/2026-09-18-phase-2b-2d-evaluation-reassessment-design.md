# Phase 2B.2D — Evaluation and Reassessment Design

**Status:** Approved  
**Scope:** Deterministic Student Pass V1 preparation evaluation and policy-transition reassessment.

## Decision

The evaluator interprets only the existing validated rule DSL; it never calls `eval`, an LLM, or an external service. It records an immutable fact snapshot, the exact assigned rule-set version, a preparation outcome, and individual findings. Outcomes remain `pass`, `manual_review`, `action_required`, or `unsupported_scope`; they are not immigration decisions.

Migration `0009` adds append-only `rule_evaluation` and `evaluation_finding`. An evaluation can supersede an earlier evaluation but never overwrite it. The evaluator runs immediately after initial assignment and may be manually retried by an officer in a later API milestone.

When activation promotes an approved release, it finds non-final cases with an initial `submitted_at` at or after the new release cutoff. It creates a superseding `case_rule_assignment`, replaces the materialized checklist only by appending requirements for the new version, and writes a superseding evaluation. Cases before the cutoff, and `COMPLETED` or `WITHDRAWN` cases, remain unchanged.

## Safety rules

- A release must be `ACTIVE`, have Student Pass scope, and match the assignment.
- Evaluation facts are copied from the student-pass profile and metadata-only document presence; snapshots never include bytes or credentials.
- Activation processes each affected case in a savepoint. One invalid case records an audit/event failure without blocking other eligible cases.
- Every reassignment references the previous assignment; every reassessment references the previous evaluation.

## Acceptance

1. A submitted case receives an immutable evaluation and findings traceable to rule versions.
2. Unsupported/missing facts lead to preparation outcomes, never approval/rejection.
3. A post-cutoff, non-final case receives a superseding assignment/evaluation after approved activation.
4. Pre-cutoff and final cases receive neither assignment nor evaluation changes.
5. Full tests, migrations, lint, formatting, mypy, and knowledge validation pass.
