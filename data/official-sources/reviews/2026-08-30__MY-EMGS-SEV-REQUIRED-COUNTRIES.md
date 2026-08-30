# Source Review — MY-EMGS-SEV-REQUIRED-COUNTRIES

- Reviewer: ImmigrationFlow project review
- Reviewed: 2026-08-30
- Decision: reviewed
- Applies to V1: yes
- Authority: Education Malaysia Global Services

## V1 findings

The page publishes a nationality list for which a Single Entry Visa is required before entry. It explicitly warns that the list may change without notice.

## Freshness and conflict handling

- The normalized list is stored separately with ISO-style country codes and its retrieval date.
- Runtime evaluation must refuse a definitive SEV answer when the dataset is older than 30 days.
- Immigration's own visa-by-country page remains the higher-authority cross-check, especially where time-limited exemptions or travel-document rules apply.
- Unknown nationality codes or discrepancies trigger manual review.

## Rule use

May determine whether the post-eVAL workflow should include an SEV preparation step, subject to freshness and cross-check controls.

