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

Project foundation, the bounded Student Pass V1 official-knowledge package, the Phase 2A logical data design, the Phase 2B.2A knowledge-sync/activation foundation, and the Phase 2B.2B/C synthetic Applicant → Officer vertical slice are implemented. The backend includes PostgreSQL migrations through revision 0008, immutable source and rule history, deterministic bundle validation, atomic synchronization, administrator review, locked activation, document-metadata capture, rule assignment at applicant handover, materialized checklists, monitoring CI, and automated tests.

The API exposes `/health`, `/health/database`, synthetic applicant draft/document-metadata/submission/checklist routes, and synthetic officer queue/processing routes. At applicant handover, a case records its applicable active rule-set version using `submitted_at`, then shows the resulting source-traceable checklist. It uses a demo-only actor header and is not a production authentication system. The knowledge pipeline and document endpoint store reviewed metadata and synthetic fixtures only—they do not store real applicant data or real sensitive file bytes. See [knowledge operations](docs/KNOWLEDGE_OPERATIONS.md) for the release sequence.

Start with the [Phase 2A design specification](docs/superpowers/specs/2026-08-30-phase-2a-erd-design.md), then review the [logical ERD](docs/architecture/STUDENT_PASS_V1_ERD.md), [data dictionary](docs/architecture/STUDENT_PASS_V1_DATA_DICTIONARY.md), [knowledge operations](docs/KNOWLEDGE_OPERATIONS.md), the [Phase 2B.2B design](docs/superpowers/specs/2026-09-18-phase-2b-2b-applicant-officer-vertical-slice-design.md), and [backend setup guide](backend/README.md).

## Getting started

Read [CONTRIBUTING.md](CONTRIBUTING.md), the [backend setup guide](backend/README.md), and [knowledge operations](docs/KNOWLEDGE_OPERATIONS.md). The next product milestone is document metadata/checklists and deterministic rule evaluation against an assigned rule-set version.

## Disclaimer

This is an independent portfolio project, not an official Malaysian government service or legal-advice product. Users must verify requirements with the relevant authorities and official sources.
