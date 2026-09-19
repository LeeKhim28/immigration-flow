# Evaluation and Reassessment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce source-traceable deterministic preparation evaluations and safely supersede them when an approved policy transition applies.

**Architecture:** Persist append-only evaluation/finding history; execute the existing bounded DSL over a JSON-safe snapshot; then invoke reassessment from activation only for cases whose `submitted_at` meets the new cutoff.

**Tech Stack:** FastAPI, Python 3.14, SQLAlchemy 2, Alembic, PostgreSQL 18, pytest.

**Spec:** `docs/superpowers/specs/2026-09-18-phase-2b-2d-evaluation-reassessment-design.md`

## Global Constraints

- `submitted_at` is the only Student Pass V1 transition cutoff.
- No automatic immigration approval, rejection, real-file storage, or external HTTP call.
- Evaluation, findings, and supersession history are append-only.

---

### Task 1: Persist evaluation history

**Files:** Create migration `0009_rule_evaluations_and_findings.py`; modify case/database models; add `test_rule_evaluation_schema.py`.

- [ ] Write failing tests proving an evaluation stores a JSON snapshot, findings reference one evaluation/rule version, and direct update/delete fails.
- [ ] Run `uv run --project backend pytest backend/tests/integration/test_rule_evaluation_schema.py -q`; expect missing models/tables.
- [ ] Add UUID tables, foreign keys, outcome checks, supersession pointer, indexes, and append-only triggers.
- [ ] Run focused schema/migration tests; commit `feat: persist rule evaluation history`.

### Task 2: Execute the bounded rule DSL

**Files:** Create `backend/app/domains/evaluations/service.py`; modify submission service; add unit/integration evaluator tests.

- [ ] Write failing tests for `eq`, `in`, `present`, `absent`, logical `all`/`any`, and a case evaluation tied to its assigned release.
- [ ] Run focused tests; expect evaluator missing.
- [ ] Implement recursive allowlisted comparison with depth already validated by the DSL; snapshot Student Pass profile and document-type presence; create findings only for fired rules.
- [ ] Evaluate after initial assignment in the existing transaction; commit `feat: evaluate assigned student pass rules`.

### Task 3: Reassess eligible cases during activation

**Files:** Modify `backend/app/knowledge/activation.py`; add activation integration tests and docs.

- [ ] Write failing tests for post-cutoff non-final reassignment/evaluation and pre-cutoff/final non-reassignment.
- [ ] Run focused activation tests; expect no case mutation.
- [ ] For each eligible case create superseding assignment, append release requirements, run superseding evaluation, and record audit/event data in a savepoint.
- [ ] Run complete verification; commit `feat: reassess cases on policy activation`.
