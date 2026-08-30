# Source Review — MY-IMMIGRATION-VISA-REQUIREMENTS-BY-COUNTRY

- Reviewer: ImmigrationFlow project review
- Reviewed: 2026-08-30
- Decision: reviewed
- Applies to V1: yes
- Authority: Immigration Department of Malaysia
- Language reviewed: Malay

## V1 findings

The page lists visa requirements, VDR/eVAL-related exemptions, travel documents that require visas, and yellow-fever certificate requirements. Some nationality treatment is explicitly time-limited.

## Automation boundary

- Do not encode temporary exemptions without effective start/end dates.
- Passport nationality alone may be insufficient when a non-standard travel document is used.
- Yellow-fever country classification must be refreshed from the linked health authority rather than frozen in the Student Pass rule set.
- Any mismatch with the EMGS SEV list triggers manual review.

## Rule use

Acts as the primary cross-check for the SEV decision and a source for manual-review triggers.

