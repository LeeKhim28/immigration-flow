# Official Source Registry

This directory records the provenance of information used by ImmigrationFlow. A source being listed does not mean every statement on the source has been converted into a rule.

## Files

- `registry.yaml` — human-reviewable source catalogue
- Future captured metadata or normalized extracts should be immutable and dated.

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

