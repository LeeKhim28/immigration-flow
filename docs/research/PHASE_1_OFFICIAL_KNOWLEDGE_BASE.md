# Phase 1 — Official Knowledge Base

## Objective

Create a trustworthy, version-controlled evidence layer for the first ImmigrationFlow journey before implementing eligibility rules, retrieval-augmented generation, or application workflows.

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

## Next step

Review the Student Pass and Graduate Pass sources one by one, create normalized extracts for the first applicant journey, then design the versioned rule format. Only after those extracts pass review should the project implement search or AI-assisted explanations.

