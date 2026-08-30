# ADR 0001: Hybrid Generic Case and Service Profile

**Status:** Accepted  
**Date:** 2026-08-30

## Context

ImmigrationFlow begins with Student Pass but is intended to demonstrate a platform that can later support other passes, permits, or citizen services. A Student Pass-only case table would be difficult to extend, while a fully generic entity-attribute-value model would weaken validation and readability.

## Decision

Use a generic `case` table for shared identity, ownership, workflow, assignment, timestamps, concurrency, and active rule-set reference. Store Student Pass-specific facts in a one-to-one `student_pass_case_profile` table.

Future services add their own profile tables only when their vertical is designed and implemented.

## Consequences

- Shared workflow and audit capabilities remain reusable.
- Student Pass fields receive explicit types and constraints.
- Adding a service requires a profile table and service-specific validation.
- Cross-service reporting may require joins, but avoids a wide nullable case table.
- The model does not attempt to predict every future immigration service.

## Rejected alternatives

- **Student Pass-only case table:** simplest now but couples the platform core to one service.
- **One wide case table:** accumulates nullable, unrelated fields as services expand.
- **JSON/EAV-first model:** flexible but makes constraints, provenance, and interviewer-readable design weaker.
