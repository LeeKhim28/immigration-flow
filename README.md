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
  decisions/            Architecture decision records
  research/             Research notes with provenance
tests/                  Cross-application and acceptance tests
```

Empty directories contain `.gitkeep` placeholders until their implementation phase begins.

## Status

Project foundation only. No production immigration advice or decision-making service is implemented yet.

## Getting started

Read [CONTRIBUTING.md](CONTRIBUTING.md), then choose a small milestone from the project scope. Avoid adding business code before the data model, source provenance, and first workflow have written acceptance criteria.

## Disclaimer

This is an independent portfolio project, not an official Malaysian government service or legal-advice product. Users must verify requirements with the relevant authorities and official sources.

