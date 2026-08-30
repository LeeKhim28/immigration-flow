# ADR 0003: Official Accepted Submission Date Determines Rule Applicability

**Status:** Proposed pending written-spec review  
**Date:** 2026-08-30

## Context

Policies commonly state that new requirements apply to applications submitted on or after a specified date. Draft creation, applicant uploads, institution preparation, Immigration receipt, and officer processing can occur on different dates. The system needs one auditable definition that respects the official transition rule.

## Decision

For Student Pass V1, an application is submitted when all required forms and documents are handed to Immigration and Immigration accepts them by issuing an official receipt or reference. Store this as `case_submission.accepted_at` and preserve the receipt as an immutable document version.

Select the applicable rule-set version at confirmation of the initial submission and preserve it as the first append-only `case_rule_assignment`:

- `accepted_at < submission_cutoff_at`: retain the previous rule-set version.
- `accepted_at >= submission_cutoff_at`: use the new rule-set version.

Later officer processing and supplementary submissions do not change applicability. A rejected handover without a receipt does not count as submission.

When a newly activated official policy explicitly covers applications submitted on or after its cutoff, automatically find affected non-final cases, create a superseding rule assignment, and re-evaluate them. Do not alter pre-cutoff cases, and do not automatically reopen completed cases.

## Consequences

- Open cases submitted before a cutoff are not unnecessarily re-evaluated under the new rules.
- New and already-in-progress cases covered by the cutoff follow the official transition date even if processing began under an older version.
- Receipt evidence and a precise accepted timestamp become mandatory for locking applicability.
- Assignment history proves why and when an affected case moved to a new version.
- If official policy defines another basis, a separate explicit applicability policy is required.

## Rejected alternatives

- **Case creation date:** occurs before official submission and can be manipulated by draft timing.
- **Officer processing date:** would change rules because of queue delays outside the applicant's control.
- **Always use latest rules:** breaks historical reproducibility and may contradict official transition language.
- **Supplementary submission date:** would unexpectedly migrate an already-submitted case to another policy version.
