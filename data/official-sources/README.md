# Official Source Registry

This directory records the provenance of information used by ImmigrationFlow. A source being listed does not mean every statement on the source has been converted into a rule.

## Files

- `registry.yaml` — human-reviewable source catalogue
- `source-record.schema.json` — machine-checkable source-record contract
- `CHANGELOG.md` — material registry and source-status changes
- `snapshots/` — dated evidence snapshots when redistribution is permitted
- `extracts/` — normalized, source-linked facts prepared for later ingestion
- `reviews/` — human review records and discrepancy notes

Git is the source of truth for Phase 1. A future runtime database or search index must be generated from reviewed material here and must never become the only copy of its provenance.

## Required source fields

- Stable internal ID
- Issuing authority and title
- Canonical URL
- Jurisdiction and topics
- Source type and language
- Retrieval and review dates
- Effective dates when explicitly published
- Status (`candidate`, `reviewed`, `superseded`, or `retired`)
- Notes and, when applicable, the ID of the replacing source

## Maintenance rules

1. Prefer primary government or officially appointed service-provider sources.
2. Never treat search snippets, blogs, or generated summaries as rules.
3. Save the exact page/document title, canonical URL, and review date.
4. Flag changed, inaccessible, contradictory, or undated material for human review.
5. Link every implemented rule to one or more source IDs and a rule version.
6. Do not silently overwrite historical evidence; supersede it.
7. Do not store personal application data, credentials, or copyrighted full-text copies without permission.
8. Re-check dynamic operational guidance before using it in a demo or rule evaluation.

## Review states

- `candidate` — discovered but not yet checked closely
- `reviewed` — authority, title, URL, topic, and applicability checked by a person
- `superseded` — retained for history and linked to its replacement
- `retired` — no longer used and has no direct replacement

`reviewed` does not mean legally guaranteed or permanently current. It means the evidence passed the documented portfolio review process on the recorded date.

