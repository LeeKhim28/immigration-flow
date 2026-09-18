# ADR 0003: Applicant Handover Date Determines Rule Applicability

**Status:** Accepted  
**Date:** 2026-08-30

## Context

Policies commonly state that new requirements apply to applications submitted on or after a specified date. Draft creation, applicant uploads, the applicant’s completed handover to Immigration, a later official receipt, and officer processing can occur on different dates. The system needs one auditable definition that respects the official transition rule and does not penalize an applicant for officer queue time.

## Decision

For Student Pass V1, an applicant has submitted when all required forms and documents are handed to Immigration. Store this boundary as non-null `case_submission.submitted_at`. A later `accepted_at`, official reference, and receipt document are separate evidence of Immigration acceptance; they must not overwrite or redefine the handover date.

Select the applicable rule-set version at confirmation of the initial submission and preserve it as the first append-only `case_rule_assignment`:

- `submitted_at < submission_cutoff_at`: retain the previous rule-set version.
- `submitted_at >= submission_cutoff_at`: use the new rule-set version.

Later officer processing, Immigration acceptance, and supplementary submissions do not change applicability. The completed handover record is the applicant-facing boundary; any exceptional rule defined by a future official policy must be modelled as an explicit new applicability basis.

When a newly activated official policy explicitly covers applications submitted on or after its cutoff, automatically find affected non-final cases, create a superseding rule assignment, and re-evaluate them. Do not alter pre-cutoff cases, and do not automatically reopen completed cases.

## Consequences

- Open cases submitted before a cutoff are not unnecessarily re-evaluated under the new rules.
- New and already-in-progress cases covered by the cutoff follow the official transition date even if processing began under an older version.
- The precise applicant handover timestamp locks applicability independently of later receipt evidence.
- Assignment history proves why and when an affected case moved to a new version.
- If official policy defines another basis, a separate explicit applicability policy is required.

## Rejected alternatives

- **Case creation date:** occurs before official submission and can be manipulated by draft timing.
- **Immigration acceptance or officer processing date:** would change rules because of queue delays outside the applicant's control.
- **Always use latest rules:** breaks historical reproducibility and may contradict official transition language.
- **Supplementary submission date:** would unexpectedly migrate an already-submitted case to another policy version.
