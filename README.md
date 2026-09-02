# ImmigrationFlow

An official-source-grounded, AI-assisted immigration case management platform for Malaysia.

ImmigrationFlow is a long-term portfolio project. Its first vertical follows an international student from study preparation through graduation and a post-study or employment pathway. The platform architecture is intended to support additional visa, pass, permit, passport, and officer workflows later without pretending that the first release covers the entire immigration system.

## Product principles

- Build one end-to-end journey deeply before expanding horizontally.
- Ground guidance in traceable, versioned official sources.
- Keep deterministic eligibility and document rules separate from generative AI.
- Use AI for explanation, extraction, and triage—not final immigration decisions.
- Protect personal data and make officer actions auditable.
- Clearly label prototypes, assumptions, stale sources, and unsupported cases.

## Initial scope

The first vertical is:

`International student → Student Pass preparation → Graduation → Graduate Pass / employment-pathway preparation`

See [docs/PROJECT_SCOPE.md](docs/PROJECT_SCOPE.md) for boundaries and success criteria.

## Repository map

```text
apps/
  applicant-web/       Applicant-facing experience
  officer-dashboard/   Review and case-management experience
backend/               Shared APIs and domain services
data/
  official-sources/    Source registry and captured source metadata
  rules/               Versioned, deterministic rules
  demo/                Synthetic demo fixtures only
docs/
  api/                  API contracts
  architecture/         System design
    decisions/          Architecture decision records
  research/             Research notes with provenance
tests/                  Cross-application and acceptance tests
```

Empty directories contain `.gitkeep` placeholders until their implementation phase begins.

## Status

Project foundation, the bounded Student Pass V1 official-knowledge package, the Phase 2A logical data design, and the Phase 2B.1 database foundation are implemented. Phase 2B.1 includes the FastAPI runtime, PostgreSQL 18.6, four Alembic revisions, fourteen domain tables, database-level integrity and immutability controls, automated tests, CI configuration, and reviewed dependency-update configuration.

The only application endpoints are `/health` and `/health/database`; there is no Case business API yet. Phase 2B.1 stores schema metadata and synthetic fixtures only—it does not store real applicant data or real sensitive file bytes.

Start with the [Phase 2A design specification](docs/superpowers/specs/2026-08-30-phase-2a-erd-design.md), then review the [logical ERD](docs/architecture/STUDENT_PASS_V1_ERD.md), [data dictionary](docs/architecture/STUDENT_PASS_V1_DATA_DICTIONARY.md), and [backend setup guide](backend/README.md). Phase 2B.2 is the next implementation boundary and has not been implemented.

## Getting started

Read [CONTRIBUTING.md](CONTRIBUTING.md) and the [backend setup guide](backend/README.md). Avoid adding Phase 2B.2 business APIs before their workflow and acceptance criteria are separately approved.

## Disclaimer

This is an independent portfolio project, not an official Malaysian government service or legal-advice product. Users must verify requirements with the relevant authorities and official sources.
