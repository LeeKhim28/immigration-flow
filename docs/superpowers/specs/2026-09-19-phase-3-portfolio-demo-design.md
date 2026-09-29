# Phase 3 Portfolio Demo Design

## Status

Approved in conversation on 2026-09-19; awaiting written-spec review before implementation planning.

## Goal

Turn the existing Student Pass backend vertical slice into a polished, locally runnable portfolio product that lets a reviewer complete and understand the synthetic Applicant-to-Officer workflow without using raw API calls.

This phase demonstrates product thinking, frontend engineering, API integration, deterministic rule evaluation, official-source provenance, and auditable workflow design. It remains an independent prototype, not a Malaysian government service, legal-advice product, or real application channel.

## Intended audience and success criteria

The primary audience is an internship recruiter, interviewer, or technical reviewer. A successful demo lets that reviewer:

1. Start the system locally using documented commands.
2. Load a deterministic synthetic scenario without entering UUIDs manually.
3. View the same case from Applicant and Officer perspectives.
4. Follow the case from preparation through formal handover and officer processing.
5. See source-backed requirements, document readiness, deterministic findings, and audit evidence.
6. Understand which behavior is implemented, which data is synthetic, and which production controls are deliberately deferred.

## Scope

### Included

- One React and TypeScript application with separate Applicant and Officer workspaces.
- A shared visual system, navigation shell, typed API client, state handling, and accessibility conventions.
- A deterministic demo bootstrap endpoint that creates or returns a complete synthetic actor, applicant profile, institution, programme, and draft Student Pass case.
- Applicant case overview, document-readiness, official-source-backed checklist, deterministic evaluation results, and formal handover action.
- Officer queue, case detail, evaluation findings, start-processing action, and audit timeline.
- Backend read APIs needed by the UI, while preserving domain services as the workflow authority.
- Local Docker/PostgreSQL and developer commands for a reproducible demo.
- Unit, integration, component, and end-to-end smoke coverage appropriate to the workflow.
- Clear prototype, privacy, provenance, and non-official disclaimers.

### Explicitly excluded

- Real authentication, accounts, identity verification, or role provisioning.
- Real personal data, passport scans, document bytes, biometrics, payments, or notifications.
- Direct integration with Immigration, EMGS, educational institutions, or other external systems.
- Official decisions, approval predictions, legal advice, or AI-controlled status changes.
- Production hosting, always-on monitoring, paid secrets management, and production object storage.
- Graduate Pass and employment-pathway execution; those remain later verticals after Student Pass V1 is demonstrably complete.
- Mobile-native applications or separate frontend deployments for each role.

## Product structure

The frontend is a single application in `apps/immigration-flow-web`. It presents two clearly separated workspaces while sharing infrastructure and styling.

### Entry experience

The landing page explains the prototype and offers:

- **Explore as Applicant** — opens the synthetic applicant case.
- **Explore as Officer** — opens the officer queue.
- **Reset demo** — recreates the known synthetic scenario after an explicit confirmation.

The interface must always show that the data is synthetic and the product is not an official service.

### Applicant workspace

The Applicant workspace contains:

1. **Case overview** — case number, stage, status, institution, programme, nationality, passport-expiry summary, and the next permitted action.
2. **Requirements and documents** — the assigned rule-set version, each requirement statement, machine-handling classification, completion state, and official-source provenance.
3. **Evaluation** — deterministic outcome summary and source-traceable findings. Copy must say “readiness result” rather than “approval decision.”
4. **Handover** — a confirmation panel that explains the submission timestamp boundary and formally submits the prepared case to Immigration in the synthetic workflow.
5. **Timeline** — append-only user-visible case milestones.

Document handling remains metadata-only. The demo may mark synthetic documents as present, but it must not imitate uploading or storing a real passport.

### Officer workspace

The Officer workspace contains:

1. **Queue** — submitted and in-process cases with status, submission time, institution, readiness summary, and a link to case details.
2. **Case detail** — applicant context required for review, checklist completion, evaluation findings, assigned rule-set version, and source provenance.
3. **Processing action** — start processing only when the case is `SUBMITTED`; invalid repeated transitions surface the API conflict without corrupting UI state.
4. **Audit timeline** — submission, rule assignment, evaluation, reassessment, assignment, and status evidence in chronological order.

No approve, reject, or predictive-risk action is included in this phase.

## Architecture

### Frontend

The web application uses:

- React 19 and TypeScript.
- Vite for local development and production builds.
- React Router for role and case routes.
- TanStack Query for server-state caching, mutations, retry control, and invalidation.
- Zod at the API boundary so malformed server responses fail visibly.
- CSS Modules plus design tokens implemented with CSS custom properties; no large component framework is required.
- Vitest and React Testing Library for component behavior.
- Playwright for one browser smoke path across both roles.

The frontend is organized by product feature rather than by generic component type. Shared code is limited to the application shell, primitives, API transport, schemas, query keys, and demo-session state.

### Backend

FastAPI remains the only server. Existing domain services retain ownership of state transitions and database writes. New API orchestration must call those services or dedicated read-query functions; route handlers must not duplicate business rules.

The backend adds:

- Demo bootstrap and reset routes, enabled only when `DEMO_MODE=true`.
- Applicant case-detail and timeline reads.
- Officer queue summaries and case-detail reads.
- Evaluation and finding reads scoped to the active actor and case.
- Official-source projection fields needed to explain checklist requirements.

The demo actor header remains explicit. The frontend obtains synthetic actor IDs from the bootstrap response and sends the correct `X-Actor-Id` for each workspace. A persistent banner labels this as demo-only authentication.

### PostgreSQL

PostgreSQL remains the source of truth. The demo seed must use existing constraints, domain services, and append-only records. Reset is allowed only for records carrying the reserved synthetic demo namespace and must never delete arbitrary cases.

No new business table is required unless implementation discovery proves an existing read projection cannot be built correctly. Read models should be assembled from the existing normalized schema before adding persistence.

## Routes and navigation

The browser routes are:

```text
/
/applicant/cases/:caseId
/applicant/cases/:caseId/requirements
/applicant/cases/:caseId/evaluation
/applicant/cases/:caseId/handover
/officer/cases
/officer/cases/:caseId
```

Direct navigation and refresh must work for every route. Unknown routes show an in-product not-found state with a link to the demo landing page.

## API boundary

All endpoints remain under `/api/v1` and return stable JSON shapes.

New conceptual contracts are:

- `POST /api/v1/demo/session` — idempotently create or retrieve the synthetic scenario and return applicant/officer actor IDs plus case ID.
- `DELETE /api/v1/demo/session` — reset only the reserved demo scenario; available only in demo mode.
- `GET /api/v1/applicant/cases/{case_id}` — applicant-owned case detail.
- `GET /api/v1/applicant/cases/{case_id}/timeline` — applicant-safe timeline projection.
- `GET /api/v1/applicant/cases/{case_id}/evaluation` — current and relevant prior deterministic evaluations.
- `GET /api/v1/officer/cases` — extend the existing queue response with presentation-safe summary fields.
- `GET /api/v1/officer/cases/{case_id}` — officer case detail, checklist, evaluation findings, and audit projection.

Every actor-scoped endpoint enforces the existing ownership or officer-role boundary. Error responses retain `{ "detail": "..." }`; the client maps HTTP status classes to user-facing recovery guidance without displaying SQL, stack traces, or credentials.

## Data flow

1. The landing page requests a demo session.
2. The backend returns stable synthetic actor and case identifiers, creating the scenario only if absent.
3. The frontend stores only those non-sensitive demo identifiers in browser storage.
4. Applicant queries include the applicant actor ID and show the draft state.
5. Synthetic document metadata and checklist information are read from PostgreSQL.
6. Formal handover invokes the existing submission service, which assigns active rules, evaluates them, records append-only evidence, and sets `submitted_at`.
7. Applicant queries are invalidated and refreshed.
8. The Officer workspace uses the officer actor ID to retrieve the queue and start processing.
9. Officer mutations invalidate queue, detail, and timeline queries so both current state and evidence update together.

## Rule and policy behavior

- The UI displays the exact assigned rule-set version and evaluation timestamp.
- Findings distinguish pass, fail, and not-applicable or unsupported outcomes using text and icons, never color alone.
- Each material requirement provides its registered official source and last-reviewed metadata when available.
- A case submitted before an official policy cutoff is not reassessed solely because a later rule activates.
- A non-final case submitted exactly at or after the cutoff is eligible for activation-time reassessment.
- Completed and withdrawn cases remain historical records and are not automatically reassessed.
- The UI explains reassessment as a new append-only evaluation, not an overwrite of the previous result.

## Visual and content direction

The product should look like a credible modern case-management service rather than a hackathon dashboard. The visual direction uses a restrained navy, teal, warm-neutral, and status palette; generous spacing; strong typography; and dense information only where officers need it.

Applicant copy is plain-language and task oriented. Officer copy is compact and evidence oriented. Both workspaces use the same terminology for status, submission, rule versions, and source provenance.

The design must avoid Malaysian government crests, official logos, or visual treatment that could imply endorsement. “ImmigrationFlow” is presented as an independent portfolio prototype.

## Accessibility and responsive behavior

- Meet WCAG 2.2 AA contrast targets for text and interactive states.
- All actions and navigation are keyboard operable with visible focus.
- Form fields have programmatic labels and contextual error messages.
- Status is communicated with text and iconography, not color alone.
- Motion respects `prefers-reduced-motion`.
- Applicant pages support phone-width layouts; officer tables collapse into labeled case cards below tablet width.
- Loading, empty, error, and success states are announced appropriately to assistive technology.

## Failure and recovery behavior

- Database or API unavailable: show a non-technical service-unavailable panel with a retry action.
- Missing demo session: recreate it idempotently rather than asking the user to copy identifiers.
- Unauthorized or wrong-role request: clear demo session state and return to the landing page with an explanation.
- Conflict during submission or processing: refetch the case and explain that its state changed.
- Invalid response shape: show a controlled data-integrity error and log only non-sensitive diagnostic context in development.
- Empty officer queue: show a valid empty state, not an error.
- Reset failure: retain the current session and do not partially clear browser state.

## Security and privacy boundaries

- Demo mode is disabled by default outside local development and tests.
- CORS permits only configured local frontend origins during this phase.
- No secrets are bundled into frontend assets.
- Browser storage contains only synthetic IDs and workspace preference.
- API logs must not contain document hashes, database URLs, or raw request bodies containing applicant context.
- Demo reset is namespaced, transactional, and tested against deletion of non-demo records.
- The README records that production use requires real authentication, authorization hardening, encrypted object storage, managed secrets, monitoring, retention controls, and always-on infrastructure.

## Testing strategy

### Backend

- Integration tests for demo bootstrap idempotency and reset isolation.
- Actor ownership and wrong-role tests for every new read route.
- Projection tests for checklist sources, evaluation findings, and timeline ordering.
- Regression tests for submission, evaluation, reassessment cutoff, and start-processing transitions.

### Frontend

- Unit tests for API schemas, status formatting, and recovery mapping.
- Component tests for loading, empty, failure, and successful states.
- Interaction tests for handover confirmation and start-processing conflict recovery.
- Accessibility assertions for landmarks, labels, focus, and status text.

### End-to-end

One Playwright smoke scenario must:

1. Open the demo landing page.
2. Enter the Applicant workspace.
3. Inspect requirements and evaluation readiness.
4. Submit the case through the confirmation flow.
5. Switch to the Officer workspace.
6. Find the submitted case and start processing.
7. Confirm the updated status and audit event.

CI runs backend tests, migration round trip, knowledge-base validation, Ruff, mypy, frontend lint, type-check, unit/component tests, production build, and the browser smoke test.

## Local operation

The preferred local experience is:

```text
docker compose up -d postgres
make demo
```

If a Makefile is not adopted, an equivalent checked-in script must start the API and frontend with clear shutdown behavior. Setup documentation must include dependency versions, database migration, demo reset, test commands, and troubleshooting.

The first release is intentionally local. A production deployment profile may later use always-on hosting, managed PostgreSQL, object storage, secrets management, and scheduled monitoring, but those costs and operational controls are not justified for the portfolio demo.

## Delivery sequence

1. Demo-session backend and read projections.
2. Frontend foundation and typed API boundary.
3. Applicant workflow.
4. Officer workflow and audit view.
5. Cross-role end-to-end test and local launcher.
6. Portfolio documentation, screenshots, and final verification.

Each slice must leave the repository runnable and tested. The implementation plan will use test-driven steps and frequent commits.

## Acceptance criteria

- A reviewer can run the complete demo locally without manually copying UUIDs or editing the database.
- Applicant and Officer experiences work through the browser and use real FastAPI/PostgreSQL state.
- The case can move from draft to submitted to in-process exactly once per allowed transition.
- The displayed checklist and evaluation cite the assigned, versioned official knowledge.
- The audit timeline proves material changes without overwriting prior evaluations.
- All displayed people, documents, and references are visibly synthetic.
- No UI control implies official approval, rejection, or legal certainty.
- Automated verification covers backend, frontend, migrations, knowledge data, and the cross-role smoke path.
- Documentation explains both the demo setup and the additional controls required before public use.
