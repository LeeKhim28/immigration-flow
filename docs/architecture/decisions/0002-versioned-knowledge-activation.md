# ADR 0002: Versioned Knowledge Synchronization and Activation

**Status:** Proposed pending written-spec review  
**Date:** 2026-08-30

## Context

Official sources can change after the application is built. The runtime database must use current approved rules without erasing the rules that governed earlier cases. GitHub already provides reviewed source and rule history, but a later application database needs queryable runtime records.

## Decision

Keep GitHub as the canonical authoring and review source. Synchronize immutable source, requirement, rule, and rule-set versions into PostgreSQL through atomic `knowledge_sync_run` records. Each synchronized version stores the originating Git commit.

New rule-set versions progress through `DRAFT` → `REVIEW` → `ACTIVE` and require a human `approval_event`. A failed sync or validation leaves the previous active version untouched. Active versions are immutable and applicability windows cannot overlap.

## Consequences

- Every evaluation can be reproduced and traced to repository evidence.
- Updating an official rule creates a new version rather than overwriting history.
- Runtime behavior changes only after validation and approval.
- Synchronization and activation require operational tooling in Phase 2B or later.
- Source monitoring may detect changes, but it cannot silently publish rules.

## Rejected alternatives

- **Database as the only source of truth:** weakens reviewable portfolio history and source diffs.
- **Overwrite the current row:** destroys reproducibility for existing cases.
- **Automatically activate detected website changes:** unsafe because page changes can be ambiguous or irrelevant.
