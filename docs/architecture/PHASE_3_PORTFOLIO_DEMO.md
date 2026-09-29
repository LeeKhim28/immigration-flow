# Phase 3 portfolio demo architecture

## Delivered vertical

Phase 3 turns the Student Pass V1 backend into one runnable browser product. A single React application exposes two role-scoped workspaces over the FastAPI/PostgreSQL platform:

```text
Reviewed Git knowledge → sync → review → approval → timed activation
                                             │
Applicant draft → policy preview → formal handover timestamp
                                             │
                              immutable assignment + evaluation
                                             │
                         Officer queue → processing + audit timeline
```

The applicant's server-recorded handover time is the policy boundary. Draft requirements are a preview only. Cases completed before a future policy cutoff are not reassessed; eligible in-progress cases submitted on or after the official cutoff can be reassessed after activation.

## Safety boundaries

- `DEMO_MODE=false` hides synthetic session endpoints by default.
- Demo identities and records use reserved synthetic references.
- Browser storage contains only synthetic actor and case identifiers.
- The UI never displays raw audit payloads or sensitive document bytes.
- AI cannot approve, reject, or mutate case state; current evaluations are deterministic.
- Reset withdraws rather than deletes cases, preserving append-only evidence.
- Official-source changes cannot directly activate policy. Synchronization, human review, administrator decision, and effective-date activation remain separate stages.

## Runtime

`make demo` orchestrates the local PostgreSQL container, Alembic, reviewed knowledge preparation, FastAPI, and Vite. `make test` uses an isolated PostgreSQL port and enforces backend, knowledge, frontend, build, and Chromium gates. GitHub Actions repeats these concerns in backend, frontend, and dependent browser-smoke jobs.

## Production gaps

This is a portfolio-quality local prototype, not a deployable government service. Public operation requires identity-provider authentication, independently reviewed RBAC/ABAC, managed and encrypted PostgreSQL, encrypted malware-scanned object storage, centralized secrets, observability and incident response, data minimization and retention enforcement, backups and disaster recovery, rate limiting and abuse controls, accessibility/security assessments, and an always-on source-monitor/activation worker. These controls are intentionally not simulated as if they already exist.
