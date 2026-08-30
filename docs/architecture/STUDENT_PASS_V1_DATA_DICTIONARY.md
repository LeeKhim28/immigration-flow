# Student Pass V1 Logical Data Dictionary

**Phase:** 2A  
**Convention:** UUID primary keys, UTC storage timestamps, and `Asia/Kuala_Lumpur` for official policy cutoffs unless the policy says otherwise.

## Identity and reference

| Entity | Purpose | Key fields | Important constraints |
|---|---|---|---|
| `actor` | Minimal reference to a person or system process | `id`, `actor_type`, `display_name`, `external_reference`, timestamps | `actor_type` is applicant, institution worker, officer, administrator, or system. Full RBAC is deferred. |
| `applicant_profile` | Applicant context without coupling identity to a service | `id`, `actor_id`, `synthetic_reference`, timestamps | V1 stores synthetic data only. At most one profile per applicant actor. |
| `institution` | Education provider reference | `id`, `institution_code`, `name`, `institution_type`, `region_code`, `active` | `institution_code` is unique. Reference state is versioned later if needed. |
| `programme` | Programme offered by an institution | `id`, `institution_id`, `programme_code`, `name`, `level`, `active` | Unique programme code within an institution. |

## Case

| Entity | Purpose | Key fields | Important constraints |
|---|---|---|---|
| `case` | Shared workflow record for any immigration service | `id`, `case_number`, `applicant_profile_id`, `service_type`, `status`, `stage`, `current_rule_set_version_id`, `created_by_actor_id`, `assigned_to_actor_id`, timestamps, `row_version` | `case_number` is unique. `row_version` increments on mutable state changes. V1 `service_type` is `STUDENT_PASS`. |
| `student_pass_case_profile` | Student Pass-specific facts | `case_id`, `application_type`, `institution_id`, `programme_id`, `institution_type`, `region_code`, `applicant_location`, `nationality_code`, `passport_expires_at`, `arrival_at` | Exactly one profile for a Student Pass case; no profile for other service types. `arrival_at` is the medical-deadline start fact. |
| `case_status_history` | Append-only status transition history | `id`, `case_id`, `from_status`, `to_status`, `reason_code`, `changed_by_actor_id`, `changed_at` | Never updated or deleted during normal operation. Status transition must be allowed by workflow policy. |

## Submission and documents

| Entity | Purpose | Key fields | Important constraints |
|---|---|---|---|
| `case_submission` | A formal Immigration handover or later supplement | `id`, `case_id`, `submission_type`, `channel`, `submitted_by_actor_id`, `accepted_at`, `immigration_reference`, `receipt_document_version_id`, `applicable_rule_set_version_id`, `confirmed_at` | At most one confirmed `INITIAL` per case. `accepted_at` requires official receipt/reference evidence. Confirmed initial submissions are immutable. The version field preserves the initial determination; later approved transitions use `case_rule_assignment`. `SUPPLEMENTARY` does not change applicability. |
| `document` | Logical document belonging to a case | `id`, `case_id`, `document_type`, `owner_actor_id`, `status`, timestamps | Contains no mutable file bytes; it groups versions. |
| `document_version` | Immutable exact document content/metadata | `id`, `document_id`, `version_number`, `storage_reference`, `content_hash`, `mime_type`, `size_bytes`, `captured_at`, `created_by_actor_id` | Unique version number per document; content hash detects duplicates/tampering. Real sensitive files are out of scope for the portfolio. |
| `submission_document` | Join between a submission and exact evidence version | `submission_id`, `document_version_id`, `purpose`, `included_at` | Composite uniqueness prevents the same version being attached twice for the same purpose. |
| `document_check` | Human or automated validation observation | `id`, `document_version_id`, `check_type`, `result`, `details`, `checked_by_actor_id`, `checked_at` | Observations are append-only. AI checks cannot change official case approval state. |

## Official knowledge

| Entity | Purpose | Key fields | Important constraints |
|---|---|---|---|
| `knowledge_source` | Stable identity of an official page/dataset | `id`, `source_code`, `authority`, `canonical_url`, `source_type`, `status` | `source_code` and canonical URL are unique where applicable. |
| `source_revision` | Immutable reviewed state of a source | `id`, `knowledge_source_id`, `retrieved_at`, `reviewed_at`, `effective_from`, `effective_to`, `content_hash`, `snapshot_reference`, `git_commit_sha` | Append-only. Supersession is explicit; old revisions remain traceable. |
| `requirement` | Stable business identity of a requirement | `id`, `requirement_code`, `service_type`, `category` | `requirement_code` is unique, for example `SPV1-REQ-014`. |
| `requirement_version` | Immutable wording and machine-handling policy | `id`, `requirement_id`, `version_number`, `statement`, `condition_expression`, `machine_handling`, `effective_from`, `effective_to`, `git_commit_sha` | Active content cannot be edited; create a new version. |
| `requirement_source` | Provenance link to exact source revision | `requirement_version_id`, `source_revision_id`, `locator`, `support_type` | Every material requirement version has at least one supporting source revision. |
| `rule_set` | Stable identity of a deployable rule family | `id`, `rule_set_code`, `service_type`, `name` | `rule_set_code` is unique. |
| `rule_set_version` | Immutable release and transition policy | `id`, `rule_set_id`, `semantic_version`, `published_at`, `effective_at`, `activated_at`, `applicability_basis`, `submission_cutoff_at`, `transition_policy`, `status`, `supersedes_version_id`, `knowledge_sync_run_id`, `git_commit_sha` | Status is `DRAFT`, `REVIEW`, `ACTIVE`, or `RETIRED`. Active applicability windows cannot overlap. `applicability_basis` is `IMMIGRATION_SUBMISSION_DATE` for Student Pass V1. |
| `rule_definition` | Stable identity of one deterministic rule | `id`, `rule_code`, `name` | `rule_code` is unique, for example `SPV1-RULE-014`. |
| `rule_version` | Immutable executable rule content | `id`, `rule_definition_id`, `rule_set_version_id`, `priority`, `condition_expression`, `outcome`, `message`, `task_type`, `git_commit_sha` | Belongs to exactly one rule-set version. No official approval outcome is allowed. |
| `rule_requirement` | Provenance from rule to requirement | `rule_version_id`, `requirement_version_id` | Every material rule has at least one supporting requirement version. |

## Evaluation and work

| Entity | Purpose | Key fields | Important constraints |
|---|---|---|---|
| `case_rule_assignment` | Append-only history of which rule-set version governs a case | `id`, `case_id`, `submission_id`, `rule_set_version_id`, `assignment_reason`, `assigned_at`, `supersedes_assignment_id`, `transition_approval_event_id` | Initial submission creates the first assignment. Only an approved transition policy may supersede it. Pre-cutoff and completed cases are not automatically reassigned. |
| `case_requirement` | Materialized checklist state for a case | `id`, `case_id`, `requirement_version_id`, `status`, `satisfied_by_document_version_id`, `updated_at` | Requirement version is fixed for that checklist item. State changes are audited. |
| `rule_evaluation` | Reproducible evaluation attempt | `id`, `case_id`, `rule_set_version_id`, `trigger`, `input_snapshot`, `outcome`, `evaluated_at`, `supersedes_evaluation_id`, `engine_version` | Append-only. Must reference exact rules and facts. Outcomes are preparation/triage only. |
| `evaluation_finding` | Individual fired rule/result | `id`, `rule_evaluation_id`, `rule_version_id`, `outcome`, `code`, `message`, `details` | Keeps user-facing explanation tied to the rule that produced it. |
| `case_task` | Human or system follow-up work | `id`, `case_id`, `task_type`, `status`, `priority`, `assigned_to_actor_id`, `due_at`, `created_from_finding_id`, timestamps | A task may be linked to a finding or deadline. Completing a task does not erase history. |
| `case_deadline` | Traceable time obligation/reminder | `id`, `case_id`, `deadline_type`, `starts_at`, `calendar_days_allowed`, `due_at`, `timezone`, `source_revision_id`, `status`, `completed_at` | `POST_ARRIVAL_MEDICAL` uses seven calendar days. Overdue status creates follow-up, not automatic rejection. |

## History and governance

| Entity | Purpose | Key fields | Important constraints |
|---|---|---|---|
| `case_event` | Append-only domain timeline | `id`, `case_id`, `event_type`, `event_payload`, `occurred_at`, `recorded_at`, `actor_id` | Records business events such as receipt confirmation and evaluation completion. |
| `audit_event` | Append-only record of who changed or accessed what | `id`, `case_id`, `actor_id`, `action`, `entity_type`, `entity_id`, `before_summary`, `after_summary`, `occurred_at` | Sensitive values should be redacted; audit records are not application logs. |
| `knowledge_sync_run` | One repository-to-database import attempt | `id`, `git_commit_sha`, `started_at`, `finished_at`, `status`, `validation_summary`, `error_summary` | Import is atomic. Failed runs cannot activate partial data. |
| `approval_event` | Human governance decision for a rule-set version | `id`, `rule_set_version_id`, `decision`, `decided_by_actor_id`, `decided_at`, `notes` | Activation requires an approval event; rejection keeps the version non-active. |

## Cross-entity invariants

1. A confirmed initial submission requires `accepted_at`, `immigration_reference`, receipt evidence, and `applicable_rule_set_version_id`.
2. Rule applicability uses the official accepted submission timestamp, not draft creation, applicant upload, supplementary delivery, or officer processing time.
3. A non-final case submitted before the cutoff retains the previous rule set. A non-final case submitted at or after the cutoff receives the new version when the policy activates, including automatic re-evaluation if it was already in progress.
4. Completed cases are historical and are not automatically reopened by a later activation.
5. An initial submission and each rule assignment cannot be edited after confirmation; transitions create superseding append-only assignments.
6. A rule evaluation and all findings reference the same rule-set version.
7. Knowledge activation is atomic, approved, and traceable to a Git commit.
8. Current case state may be updated, but every material transition creates status/event/audit history.
9. No entity or rule may represent automated Immigration approval or rejection.
