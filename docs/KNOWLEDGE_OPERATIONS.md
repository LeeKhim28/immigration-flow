# Knowledge release operating sequence

ImmigrationFlow treats the reviewed Git repository as the canonical authoring
source. PostgreSQL stores immutable runtime history; it never silently edits a
published rule when an official page changes.

## Local workflow

1. Keep the checkout clean and validate the source registry, requirements, and
   rules with `ruby scripts/validate_knowledge_base.rb`.
2. Run the locked backend tests and apply migrations with `alembic upgrade
   head` against the test database.
3. Synchronize the exact repository commit:

   ```text
   python -m app.knowledge.cli sync --root . --git-sha <commit-sha>
   ```

4. Submit the resulting rule-set version for review. A successful sync is
   required before the status can move from `DRAFT` to `REVIEW`.
5. An `ADMINISTRATOR` records exactly one approval or rejection. Approval does
   not immediately change the active release.
6. Activation runs at or after `effective_at` and atomically retires the prior
   active version before activating the approved version:

   ```text
   python -m app.knowledge.cli activate-due --at <offset-aware-iso-time>
   ```

The application startup catch-up and optional poller use the same coordinator.
Set `KNOWLEDGE_ACTIVATION_POLL_SECONDS=0` for a demo environment when no
background polling is desired. A real deployment can use an always-on worker
once secret management, monitoring, and operating costs are approved.

## Safety boundaries

- A source monitor can open a review issue, but it cannot publish or activate a
  rule release.
- Every requirement version and rule version must retain source provenance.
- Rule and approval history is append-only at the PostgreSQL boundary.
- Student Pass V1 applicability is based on the recorded immigration
  submission date. A release effective date does not retroactively change a
  case that was already formally submitted.
- Error output is bounded and never includes database URLs, secrets, response
  bodies, or applicant data.
