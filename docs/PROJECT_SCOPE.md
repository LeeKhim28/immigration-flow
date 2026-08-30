# Project Scope

## Problem

People preparing Malaysian immigration applications must reconcile requirements, documents, deadlines, and status information spread across multiple official sources and service providers. Applicants can struggle to understand what applies to their situation, while officers and institutions need consistent case preparation, traceability, and review workflows.

## Project goal

Build a credible portfolio prototype of an immigration case-management platform that demonstrates product thinking, full-stack engineering, data provenance, rule modelling, responsible AI, testing, and security awareness.

## V1 vertical

V1 follows one coherent journey for an international higher-education student:

1. Create a case and capture applicant context.
2. Identify the relevant Student Pass preparation pathway.
3. Produce a source-backed document checklist.
4. Validate document presence, type, and basic expiry/format constraints.
5. Track case states and surface missing information.
6. Present an officer/institution review queue with an audit trail.
7. Support graduation transition research for Graduate Pass or an employment-related pathway without automatically declaring eligibility.

## V1 users

- International student or graduate
- Education-institution case worker
- Immigration-style reviewing officer (synthetic portfolio persona)
- Project administrator maintaining sources and rules

## In scope

- Applicant and reviewer experiences
- Shared case, document, source, rule, decision-support, and audit concepts
- Official-source registry with retrieval and review dates
- Versioned deterministic rules and human-readable explanations
- AI-assisted document extraction, summarisation, and triage behind explicit safeguards
- Synthetic demo data and automated tests
- Accessibility, privacy, and security requirements appropriate to a portfolio prototype

## Explicitly out of scope for V1

- Submitting real applications to any government system
- Making, predicting, or representing official approval decisions
- Legal advice or guaranteed eligibility outcomes
- Production storage of passports or real personal data
- Complete coverage of all Malaysian visas, passes, permits, border functions, or passports
- Biometric verification, payment processing, or integrations presented as official
- Large-scale business implementation before the first workflow and source model are validated

## Architecture direction

The first vertical should use reusable platform capabilities:

- Case and workflow engine
- Versioned rule engine
- Document and validation engine
- Official-source and provenance layer
- Role-based access control and audit log
- AI assistance layer separated from deterministic rules

Additional services—professional visit, foreign worker, dependant, other passes, passport, and travel documents—remain future modules rather than V1 promises.

## Success criteria

- A new reviewer can run a synthetic case through the complete V1 workflow.
- Every material requirement shown to a user links to a registered official source and records when it was checked.
- Rule evaluations are reproducible for a specified rule version and effective date.
- AI output is distinguishable from official rules and never changes case approval state by itself.
- Tests cover the happy path, missing/expired documents, unsupported cases, stale sources, and role restrictions.
- The README, architecture notes, demo, and commit history explain the engineering decisions clearly to an interviewer.

## Next milestone

Write the first user journey and acceptance tests, design the core case/source/rule data model, and research the exact official requirements needed for that journey. Do not expand to unrelated immigration services until this vertical works end to end.

