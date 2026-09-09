# Phase 2B.2A Versioned Knowledge Synchronization and Activation Design

**Status:** Awaiting written-spec approval
**Date:** 2026-09-02
**Scope:** Student Pass V1 knowledge monitoring, repository-to-PostgreSQL synchronization, governance, and scheduled rule-set activation. Case assignment and evaluation are deferred to Phase 2B.2B.

## 1. Purpose

Phase 2B.2A turns the reviewed Student Pass V1 official-source, requirement, and rule artifacts in GitHub into an auditable runtime knowledge database. It must let ImmigrationFlow notice possible official-source changes, preserve every reviewed version, validate provenance, require a human governance decision, and change runtime rules only at the approved effective time.

The design preserves two distinct sources of truth:

- GitHub is the canonical authoring and review history for source records, evidence reviews, requirements, rules, schemas, and monitor baselines.
- PostgreSQL is the queryable runtime record of immutable reviewed versions, synchronization attempts, approvals, and active rule releases.

No detected webpage change may directly alter a requirement, rule, or active runtime version.

## 2. Delivery boundary

Phase 2B.2 is split into two separately reviewed increments:

1. **Phase 2B.2A — Knowledge Sync and Activation:** source monitoring, immutable knowledge and rule versions, atomic synchronization, approval, and time-based activation.
2. **Phase 2B.2B — Case Assignment and Re-evaluation:** rule-set assignment at accepted Immigration submission, case evaluation, findings, tasks, deadlines, and approved policy-transition re-evaluation.

Phase 2B.2A does not add Applicant, Institution, or Officer business APIs. It does not assign rules to cases, evaluate cases, create case tasks, or implement automatic case re-evaluation. The deferred `case.current_rule_set_version_id` and `case_submission.applicable_rule_set_version_id` columns are introduced in Phase 2B.2B so Phase 2B.2A does not leave half-wired nullable relationships.

## 3. Deployment choice and future migration

### 3.1 Portfolio-first V1

The current project uses a portfolio-first operating model:

- GitHub Actions performs the daily official-source check and supports a manual dispatch.
- GitHub Issues provide the human review queue for changed or blocked sources.
- The local application synchronizes reviewed GitHub content into PostgreSQL when explicitly requested.
- The activation coordinator runs when the application starts, when an administrator invokes it, and periodically while the local application remains running.

This choice avoids cloud database fees, always-on compute fees, production secret management, and operational security work that a demo does not yet need.

### 3.2 Public-production target

Before ImmigrationFlow is offered to the public, monitoring, synchronization, and activation should run through an always-on worker backed by persistent cloud PostgreSQL and managed secret storage. The worker will use the same monitor, validator, synchronization, governance, and activation interfaces defined here. The migration changes the scheduler and deployment adapters, not the core knowledge model or rule semantics.

In portfolio-first mode, a computer that is turned off cannot activate a local rule release at the exact effective instant. The next application start must perform a catch-up activation immediately. The future always-on deployment removes that limitation.

## 4. Architecture and component boundaries

The subsystem contains four independently testable components.

### 4.1 Source Monitor

The Source Monitor reads only approved monitoring entries from the repository, retrieves the configured official HTTPS resources, normalizes relevant content, calculates hashes, and reports observations. It cannot edit the repository, write formal knowledge versions, approve releases, or activate rules.

### 4.2 Knowledge Validator

The Knowledge Validator extends the existing source, requirement-set, rule-set, and policy-contract validation. It validates references, supported expression grammar, semantic versions, provenance, transition metadata, and monitor configuration before synchronization is allowed.

### 4.3 Knowledge Sync

Knowledge Sync imports a specific clean Git commit into PostgreSQL. It is idempotent for a previously successful commit, creates immutable versions only when reviewed content changes, and commits a complete import atomically.

### 4.4 Activation Coordinator

The Activation Coordinator finds approved releases whose `effective_at` has arrived, obtains a PostgreSQL lock for the rule set, revalidates activation invariants, retires the prior active release, activates the new release, and writes audit evidence in one transaction.

These components communicate through explicit data structures and application services. Source retrieval, GitHub Issue operations, Git access, clocks, and database sessions remain replaceable adapters so core behavior can be tested without live websites or GitHub writes.

## 5. Official-source monitoring

### 5.1 Monitoring scope

Monitoring is opt-in. Initial entries cover reviewed official sources materially referenced by the Student Pass V1 requirement and rule artifacts. Candidate sources, discovery-only portals, dynamic operational lists excluded from stable rules, and unrelated immigration services are not automatically monitored until separately reviewed.

A versioned repository file, `data/official-sources/monitoring-baselines.yaml`, records for each monitored source:

- source ID;
- canonical HTTPS URL;
- normalization strategy and its version;
- optional content selector or extraction rule;
- approved normalized-content hash;
- baseline capture time; and
- Git commit that approved the baseline.

The baseline contains no full webpage copy. Updating a baseline is a reviewed repository change and normally accompanies any necessary source review, requirement, or rule update.

### 5.2 Normalization and comparison

For HTML sources, normalization removes scripts, styles, navigation, cookie banners, repeated layout material, comments, and insignificant whitespace before hashing the configured content region. Source-specific selectors are allowed when a stable main-content region cannot be selected generically. A normalization-strategy version change invalidates comparison until a new baseline is reviewed.

V1 stores only URL and retrieval metadata, the normalized hash, a bounded change summary, reviewed evidence locators, and the Git commit. It does not persist complete HTML or complete official documents in PostgreSQL.

### 5.3 Outcomes

Monitor outcomes are operational observations and are separate from the authoring statuses `candidate`, `reviewed`, `superseded`, and `retired` in the source registry.

- `UNCHANGED`: retrieval and normalization succeeded and the hash matches the approved baseline.
- `CHANGED`: retrieval succeeded and the hash differs from the approved baseline.
- `BLOCKED`: three consecutive scheduled checks could not obtain a comparable result.

There is no `FETCH_FAILED` source status. A transient timeout, DNS failure, server error, or parsing failure retains the prior source outcome and records a sanitized error code, message, and check time in the workflow result. One successful comparable check resets the consecutive-failure count.

The workflow makes a bounded number of attempts per run but counts at most one failure toward the daily streak. A small `monitor-state.json` workflow artifact carries hashes and failure counters between scheduled runs. It is operational state, not canonical policy evidence. If the artifact is unavailable or expired, the workflow safely restarts the streak from zero and never changes formal rules. The future always-on deployment moves this operational state to durable storage.

### 5.4 GitHub review issues

A `CHANGED` or `BLOCKED` outcome creates or updates one open GitHub Issue identified by a stable source-ID marker. The issue includes only public-source metadata, the previous and observed hashes when available, check times, a bounded change summary, and review instructions. It must not contain application data, secrets, cookies, response headers containing credentials, or a complete copied webpage.

Repeated checks update the existing issue instead of opening duplicates. Closing an issue records completion of human review but does not itself update a baseline, synchronize PostgreSQL, or activate a rule. Formal changes still require a reviewed Git commit.

The dedicated monitor workflow receives only `contents: read` and `issues: write`. Existing backend pull-request CI remains read-only.

### 5.5 Retrieval safety

The monitor accepts only repository-approved HTTPS URLs and applies:

- an allowlist of reviewed official hostnames;
- DNS and redirect checks that reject loopback, link-local, private, and other non-public destinations;
- a small redirect limit;
- response-size, timeout, and retry limits;
- an identifiable, rate-limited user agent; and
- no CAPTCHA solving, robots bypass, authentication bypass, or safety-interstitial bypass.

An official site that cannot be monitored safely becomes `BLOCKED` after the agreed failure threshold and is routed to manual review.

## 6. PostgreSQL model

Phase 2B.2A adds twelve tables in two migrations.

### 6.1 Migration `0005_knowledge_sources_and_requirements`

| Table | Purpose | Principal fields and constraints |
|---|---|---|
| `knowledge_sync_run` | Durable record of one import attempt | Git commit SHA, start/end timestamps, status, validation summary, sanitized error summary. Multiple failed attempts for one commit are allowed; at most one successful run per commit. |
| `knowledge_source` | Stable identity of an official source | Unique source code and canonical URL, authority, source type, and authoring status. |
| `source_revision` | Immutable reviewed source state | Source FK, retrieval/review/effective timestamps, normalized content hash, repository snapshot reference, Git commit SHA, and sync-run FK. |
| `requirement` | Stable requirement identity | Unique requirement code, service type, and category. |
| `requirement_version` | Immutable reviewed requirement content | Requirement FK, monotonic version number, statement, validated condition document, machine-handling policy, effective interval, fingerprint, Git commit SHA, and sync-run FK. |
| `requirement_source` | Exact provenance for a requirement version | Composite identity over requirement version, source revision, locator, and support type. |

### 6.2 Migration `0006_rule_versions_and_activation`

| Table | Purpose | Principal fields and constraints |
|---|---|---|
| `rule_set` | Stable deployable rule-family identity | Unique rule-set code, service type, and name. |
| `rule_set_version` | Immutable release and transition policy | Rule-set FK, semantic version, published/effective/activated timestamps, applicability basis, submission cutoff, transition policy, status, superseded-version FK, sync-run FK, fingerprint, and Git commit SHA. |
| `rule_definition` | Stable rule identity | Unique rule code and name. |
| `rule_version` | Immutable deterministic rule content | Rule-definition FK, rule-set-version FK, priority, validated condition document, outcome, message, optional task type, fingerprint, and Git commit SHA. |
| `rule_requirement` | Provenance from rule to requirement | Composite identity over rule version and requirement version. |
| `approval_event` | Append-only human governance decision | Rule-set-version FK, decision, administrator actor FK, decision timestamp, and notes. |

JSONB may store already schema-validated condition and transition documents. It must not store executable Python, templates, or arbitrary code.

Revision `0006` also broadens the existing `audit_event` table for platform-level knowledge governance. `case_id` becomes nullable only when `entity_type` identifies an approved knowledge-governance entity. A database check rejects a null case for ordinary case audit events. An `(entity_type, entity_id, occurred_at)` index supports knowledge audit queries. This change avoids inventing a second generic audit system while preserving the existing case-audit requirement.

## 7. Version identity and immutability

Stable entities (`knowledge_source`, `requirement`, `rule_set`, and `rule_definition`) are addressed by reviewed business codes. Revision and version records are immutable.

A canonical fingerprint includes every field that affects meaning plus sorted provenance references. Therefore a wording, condition, machine-handling instruction, evidence locator, support type, outcome, priority, or referenced requirement change creates a new version. Cosmetic YAML ordering does not.

For each stable requirement, sync assigns the next monotonic integer version when the fingerprint changes. A rule version belongs to exactly one rule-set version. A synchronized rule-set semantic version is immutable: changing its release fingerprint without incrementing the semantic version is rejected.

Database triggers prohibit update and delete operations on:

- `source_revision`;
- `requirement_version` and `requirement_source`;
- `rule_set_version` content other than the controlled status/activation transition;
- `rule_version` and `rule_requirement`; and
- `approval_event`.

Controlled rule-set status changes must use the activation service and are additionally constrained in PostgreSQL. History is never represented by overwriting a previous version.

## 8. Provenance and release invariants

PostgreSQL constraints and deferred constraint triggers enforce invariants at transaction commit, including writes that bypass Python:

1. Every material requirement version has at least one supporting source revision.
2. Every rule version has at least one supporting requirement version.
3. Referenced source and requirement versions belong to the same successful synchronization release or to an explicitly reused earlier immutable version.
4. A rule-set version contains at least one rule and all rule versions reference valid outcomes from its declared outcome contract.
5. All records synchronized as one release are traceable to the requested Git commit.
6. An `ACTIVE` version has a successful sync run and exactly one `APPROVED` decision.
7. A rejected immutable version can never later become approved or active; corrections require a new semantic version.
8. One rule set cannot have overlapping active applicability windows.
9. Student Pass V1 uses `IMMIGRATION_SUBMISSION_DATE` and requires explicit submission-cutoff and transition-policy metadata for a policy that changes existing applicability.
10. No rule outcome represents automated Immigration approval or rejection.

The database verifies at approval insertion that `decided_by_actor_id` currently references an `ADMINISTRATOR`. `SYSTEM`, `OFFICER`, `INSTITUTION_WORKER`, and `APPLICANT` actors cannot approve or reject a release.

## 9. Atomic and idempotent synchronization

The synchronization command operates only on a clean checkout and requires an explicit Git commit SHA equal to the checked-out commit. Before database writes it runs all source schemas, requirement schemas, rule schemas, monitor-baseline validation, DSL validation, and policy-contract tests.

Synchronization uses two transaction boundaries so failures remain observable without exposing partial policy data:

1. Create and commit a `knowledge_sync_run` in `STARTED` state.
2. Import or reuse all stable entities, immutable versions, provenance links, and draft releases and mark that run `SUCCEEDED` in one transaction.
3. Commit the formal import and `SUCCEEDED` transition together.
4. If validation or import fails, roll back the import transaction and use a separate short transaction to mark the already-created run `FAILED` with a bounded, sanitized summary.

The formal import can never be committed while its sync run remains `STARTED`. It cannot commit unless all deferred provenance and release constraints pass. A successful sync of an already successful Git commit is a no-op that returns the existing result. A failed commit may be retried, but only one successful run may exist for it. If a process stops after creating the run but before completing the import, a later recovery marks the stale `STARTED` run `FAILED`; no formal rows from that run exist.

Sync creates rule-set versions as `DRAFT` only. It never writes an approval and never activates a release.

## 10. Review, approval, and scheduled activation

The persisted rule-set statuses remain `DRAFT`, `REVIEW`, `ACTIVE`, and `RETIRED`, consistent with ADR 0002.

- `DRAFT → REVIEW` is allowed only after a complete validation and provenance check.
- An administrator may append one `APPROVED` or `REJECTED` approval event while the version is in `REVIEW`.
- A future-effective approved version remains persisted as `REVIEW`. The application derives the display state `SCHEDULED` from an approval plus `effective_at > now`; `SCHEDULED` is not an additional stored status.
- `REVIEW → ACTIVE` is performed only by the Activation Coordinator at or after `effective_at`.
- The prior `ACTIVE` version becomes `RETIRED` in the same transaction.

Official timestamps use their stated timezone. When a policy does not state one, ImmigrationFlow interprets the cutoff in `Asia/Kuala_Lumpur` and stores the resolved instant as `timestamptz` together with the applicability metadata needed to explain the interpretation.

The Activation Coordinator uses a per-rule-set PostgreSQL advisory or row lock. It rechecks approval, successful synchronization, effective time, supersession, and non-overlap under the lock. The old release remains active if any check or write fails. A successful switch writes a platform-level `audit_event` with a null `case_id`, an approved knowledge `entity_type`, the rule-set-version ID, and bounded before/after status summaries. It does not create case assignments; Phase 2B.2B consumes the activation history later.

## 11. Rule-expression safety

Phase 2B.2A validates and stores rule expressions but does not execute them against cases. Expressions use the bounded YAML/JSON DSL already represented in the Student Pass V1 artifacts. Validation uses an allowlist of logical forms, fact identifiers, operators, scalar/list value types, outcomes, and task types.

The implementation must not call Python `eval`, `exec`, dynamic imports, shell evaluation, or a general-purpose template engine. Unknown operators, unknown fields, excessive nesting, invalid value types, and unsupported outcomes fail synchronization.

## 12. Failure behavior and observability

- Monitor failure never changes an active rule.
- Hash difference means review required, not confirmed policy change.
- Sync failure leaves formal version tables unchanged and persists only the failed run summary.
- Approval failure leaves the version in `REVIEW` with no partial decision.
- Activation failure leaves the prior version `ACTIVE` and records a sanitized diagnostic event.
- Concurrent sync for the same commit and concurrent activation for the same rule set are serialized or rejected safely.
- Logs, workflow summaries, issues, and database error summaries exclude secrets, local environment values, cookies, and personal data.

Operational errors are distinguishable by stable error codes. Human-readable messages may explain the failing source, artifact, constraint, or activation step without copying sensitive payloads.

## 13. Testing strategy

### 13.1 Source monitor tests

Committed synthetic HTML fixtures test normalization, ignored layout changes, material content changes, redirect and address rejection, size and timeout limits, transient error handling, streak reset, third-consecutive-failure blocking, and GitHub Issue deduplication. Pull-request CI does not depend on live official websites. The scheduled workflow is the only routine job that performs live source retrieval.

GitHub operations are tested through a fake issue adapter. Tests do not create real issues.

### 13.2 Synchronization and schema tests

PostgreSQL integration tests prove:

- repeat sync of one commit is idempotent;
- changed semantic content creates new immutable versions;
- unchanged content reuses existing versions;
- semantic-version reuse with changed release content is rejected;
- missing requirement-source and rule-requirement provenance is rejected at commit;
- an import failure leaves no partial formal data and records a failed sync run;
- direct SQL cannot update or delete immutable history;
- only an administrator can create an approval decision; and
- rejection is final for the immutable release.

### 13.3 Activation tests

Clock-controlled PostgreSQL tests prove:

- future approved releases do not activate early;
- due releases atomically retire the old version and activate the new one;
- missing approval, failed sync, overlap, and invalid transition metadata prevent activation;
- a failed switch preserves the previous active version;
- concurrent activation cannot create two active versions; and
- application-start catch-up activates an overdue approved release.

### 13.4 Migration and regression tests

The live PostgreSQL migration suite performs `0004 → head → 0004 → head`, verifies the exact linear Alembic graph, checks model/migration parity, and confirms all constraints and triggers. The existing backend, knowledge-base, and policy-contract suites remain green. All fixtures are synthetic and no real applicant data or document bytes are introduced.

## 14. Continuous integration

Backend CI adds schema, monitor-fixture, sync, activation, and migration tests while preserving read-only repository permissions. A separate scheduled and manually dispatchable source-monitor workflow has only `contents: read` and `issues: write`.

The scheduled workflow:

1. restores the latest operational monitor-state artifact when available;
2. validates the monitor configuration;
3. performs one bounded check per enabled source;
4. calculates outcomes and updates deduplicated review issues only for `CHANGED` or `BLOCKED`;
5. uploads the next sanitized state artifact; and
6. fails visibly for workflow defects without changing formal knowledge artifacts.

Dependabot proposals remain subject to human review and the normal CI checks.

## 15. Acceptance criteria

Phase 2B.2A is complete only when:

1. Twelve migration-managed knowledge, rule, sync, and approval tables exist through revisions `0005` and `0006`, and the existing `audit_event` safely supports constrained platform-level knowledge audit entries.
2. Versioned content and provenance are immutable and enforced at the PostgreSQL boundary.
3. Every formal requirement and rule has complete, exact provenance.
4. A clean, explicit Git commit can be synchronized atomically and idempotently.
5. Failed synchronization is recorded without partial formal data.
6. Only an `ADMINISTRATOR` can approve or reject a release.
7. Approved future releases remain non-active until their effective time.
8. Activation is locked, atomic, auditable, and failure-safe.
9. Daily and manual monitoring classify sources without silently changing rules.
10. A changed or blocked source creates or updates one sanitized GitHub Issue.
11. The third consecutive scheduled retrieval failure produces `BLOCKED`; earlier transient errors do not create a source failure status.
12. Full-page snapshots, secrets, real applicant data, and real document bytes are not stored or published.
13. Existing Phase 1, Phase 2A, and Phase 2B.1 tests continue to pass.
14. No case rule assignment, case evaluation, re-evaluation, business API, or automated Immigration decision is introduced.
15. Documentation clearly records the portfolio-first limitation and the always-on public-production migration path.

## 16. Phase 2B.2B handoff

Phase 2B.2B will use the immutable active releases and activation history created here to implement:

- the initial `case_rule_assignment` at confirmed Immigration acceptance;
- `case.current_rule_set_version_id` and `case_submission.applicable_rule_set_version_id`;
- reproducible rule evaluations and findings;
- case requirements, tasks, and seven-calendar-day deadlines; and
- automatic reassignment and re-evaluation only when an approved policy explicitly covers a non-final case whose Immigration-accepted submission is on or after the official cutoff.

Cases accepted before the cutoff retain their previous rule version, and completed cases are not automatically reopened, as required by ADR 0003.
