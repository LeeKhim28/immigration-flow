# Phase 1 — Official Knowledge Base

## Objective

Create a trustworthy, version-controlled evidence layer for the first ImmigrationFlow journey before implementing eligibility rules, retrieval-augmented generation, or application workflows.

## Completion status

The bounded Student Pass V1 knowledge package is complete as of 2026-08-30 for new UA/IPTS higher-education applicants applying from outside Malaysia for Peninsular Malaysia. It includes reviewed sources, normalized requirements, a rule contract, deterministic rules, dynamic-dataset freshness controls, and synthetic cases.

Renewal, variation, progression, dependants, school/language/training-centre applications, and Sabah/Sarawak processes remain explicitly unsupported by this rule set.

## Why it starts in GitHub

The Phase 1 knowledge base is intentionally file-based. Git provides reviewable diffs, history, source attribution, and a simple portfolio narrative. It is not the production query database.

Later, a build or ingestion process may transform reviewed records and extracts into PostgreSQL, a search engine, or a vector index. Those generated stores must retain source IDs, review dates, effective dates, and content versions so every answer can be traced back to this repository.

## Phase 1 deliverables

- A schema-validated official-source registry
- A narrow catalogue for Student Pass, arrival, medical-screening, graduation, and Graduate Pass research
- Defined review and supersession states
- Locations for dated snapshots, normalized extracts, and review notes
- A changelog for material knowledge-base changes
- A clear boundary between evidence, deterministic rules, and AI-generated explanations

## Trust pipeline

```text
Official source discovered
        ↓
Candidate registry record
        ↓
Human authority/applicability review
        ↓
Dated snapshot or review note (when appropriate)
        ↓
Normalized source-linked extract
        ↓
Versioned deterministic rule or searchable index
        ↓
User-facing explanation with citations and limitations
```

## Acceptance criteria

- Every registered item uses an official authority or officially appointed service provider.
- Every record has a stable ID, canonical HTTPS URL, retrieval date, topics, type, language, and status.
- A reviewed source records a human review date.
- Candidate sources cannot silently become eligibility rules.
- Superseded sources remain in history and identify their replacement when one exists.
- Runtime-derived records remain traceable to source ID and version.
- No real applicant data or secrets are stored in the knowledge base.

## Not included yet

- Automated website crawling
- Full-page copyrighted archives without permission
- Embeddings or a vector database
- RAG prompts or chat responses
- Eligibility determinations
- Coverage of every Immigration Department service

## Phase 2A handoff

The logical Student Pass V1 data model is approved in `docs/superpowers/specs/2026-08-30-phase-2a-erd-design.md`. Its ERD, data dictionary, and architecture decisions define the generic-case/service-profile model, immutable knowledge versions, official-submission cutoff behavior, and re-evaluation policy.

The next milestone is Phase 2B: translate the approved logical model into reviewed PostgreSQL types, constraints, migrations, and database-level tests without expanding the product beyond the Student Pass V1 vertical.
