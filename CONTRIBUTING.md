# Development Guide

## Working agreement

- Keep changes small, reviewable, and tied to a documented user need.
- Use synthetic data only. Never commit passports, identity numbers, real applications, credentials, or secrets.
- Cite official source IDs in rule definitions and tests.
- Separate deterministic rules from AI prompts and model output.
- Add or update tests whenever behavior changes.
- Record important architectural trade-offs in `docs/architecture/decisions/`.
- Use Alembic migrations for every schema change and include migration tests that exercise upgrade, downgrade, and restoration behavior where applicable.
- Never create the application schema with `Base.metadata.create_all()` or an equivalent direct schema-creation shortcut; tests must exercise the migrations used by the application.
- Use synthetic fixtures only. Do not copy real applicant records, real identity or passport values, or real sensitive file bytes into code, tests, documentation, or logs.
- Review every dependency-update pull request manually. Confirm tests, release notes, compatibility, and security impact before merging; dependency automation must not auto-merge changes.

## Suggested commit style

```text
feat: add graduate pass case state model
test: cover expired passport validation
docs: record rule versioning decision
refactor: separate eligibility rules from AI explanation
```

## Before opening a pull request

1. Confirm the change stays within the current milestone.
2. Run the relevant formatters and tests. Schema changes must pass the migration round trip and the complete integration suite against the isolated `_test` database.
3. Check that demo data is synthetic and logs expose no personal data.
4. Check that user-facing requirements have source references and review dates.
5. Explain limitations and manual-review paths.
6. Review dependency changes manually and confirm CI evidence before merging.

## Branches

Use short-lived branches such as `feat/case-model` or `docs/source-registry`. Keep the default branch releasable and avoid committing generated artifacts unless they are intentionally reviewed deliverables.
