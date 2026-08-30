# Source Review — MY-EMGS-STUDENT-PASS-REQUIRED-DOCUMENTS

- Reviewer: ImmigrationFlow project review
- Reviewed: 2026-08-30
- Decision: reviewed
- Applies to V1: yes
- Authority: Education Malaysia Global Services

## Scope checked

Only the New Student Pass Application section was extracted. Renewal, variation, progression, and Sarawak additions are excluded from V1.

## V1 findings

The applicant-facing set includes a compliant photo, specified passport pages, an offer letter, health declaration, academic certificates/transcripts, and English-language evidence. Passport validity must be at least 18 months. Applicants from Libya, Iran, Iraq, Somalia, Sudan, Syria, and Yemen must provide all passport pages.

Conditional/institution-managed items include the Sudan NOC, Iran LOE, personal bond, yellow-fever evidence when applicable, and institution-specific additional academic requirements.

## Interpretation notes

- The 18-month passport duration is encoded as a hard preparation check; the longer course-duration-plus-12-month wording is a recommendation, not a hard failure.
- Missing English evidence is encoded as `action_required`, with a warning that it can delay processing and affect full-course-duration issuance; the system does not invent minimum scores.
- Personal Bond is required but can be completed for endorsement after arrival, so it is not a pre-submission applicant blocker.
- The source contains Sarawak-only additions; those trigger `unsupported_scope` in V1.

## Rule use

May support document presence, conditional-document, passport-duration, and accepted-English-evidence rules.

