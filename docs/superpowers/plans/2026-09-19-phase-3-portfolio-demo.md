# Phase 3 Portfolio Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a polished local browser demo that carries one synthetic Student Pass case from applicant preparation through Immigration handover and officer processing using the real FastAPI/PostgreSQL workflow.

**Architecture:** One React/TypeScript/Vite frontend contains separated Applicant and Officer workspaces and talks to actor-scoped FastAPI endpoints through a Zod-validated API client. FastAPI owns demo bootstrap and read projections while existing domain services remain the only workflow mutation authority; PostgreSQL remains the source of truth and stores append-only evidence.

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy 2, PostgreSQL 18, Alembic, React 19, TypeScript, Vite, React Router, TanStack Query, Zod, CSS Modules, Vitest, React Testing Library, Playwright, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-19-phase-3-portfolio-demo-design.md`

## Global Constraints

- All applicants, identifiers, documents, and references are visibly synthetic; no real personal data or document bytes are stored.
- The product is labelled an independent portfolio prototype, not an official Malaysian government service or legal-advice product.
- `DEMO_MODE` is disabled by default outside local development and tests.
- Existing ownership, officer-role, append-only history, submission-cutoff, and rule-version semantics remain authoritative.
- No control may approve, reject, predict approval, or allow AI to change case status.
- Browser storage contains only synthetic actor/case identifiers and workspace preference.
- Applicant layouts support phone widths; officer tables become labelled cards below tablet width.
- Status meaning cannot depend on color alone and interactive controls must be keyboard accessible.
- Production use remains documented as requiring real authentication, managed secrets, encrypted object storage, monitoring, retention controls, and always-on infrastructure.

## Review Focus

- A stale browser session that references a reset case must recreate the demo session and recover without a blank screen (Task 4 test).
- Two simultaneous bootstrap requests must return one scenario rather than duplicate actors or cases (Task 1 integration test).
- A non-demo database row must survive demo reset unchanged (Task 1 integration test).
- A submission or start-processing `409` caused by another tab must refetch current state and explain the conflict (Tasks 5 and 6 interaction tests).
- A malformed successful API response must be rejected by Zod and rendered as a controlled data-integrity failure (Task 3 unit and component tests).

---

### Task 1: Safe synthetic demo session

**Files:**
- Create: `backend/app/api/demo.py`
- Create: `backend/app/domains/demo/__init__.py`
- Create: `backend/app/domains/demo/service.py`
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/main.py`
- Modify: `.env.example`
- Test: `backend/tests/integration/test_demo_api.py`
- Test: `backend/tests/unit/test_config.py`

**Interfaces:**
- Consumes: existing `Actor`, `ApplicantProfile`, `Institution`, `Programme`, `Case`, and Student Pass workflow models.
- Produces: `POST /api/v1/demo/session -> DemoSessionResponse`; `DELETE /api/v1/demo/session -> 204`; `DemoSessionService.get_or_create(session) -> DemoSession`; `DemoSessionService.reset(session) -> None`.

- [ ] **Step 1: Write failing configuration and API tests**

```python
def test_demo_mode_defaults_to_disabled(monkeypatch):
    monkeypatch.delenv("DEMO_MODE", raising=False)
    assert Settings().demo_mode is False

def test_demo_session_is_idempotent(client, demo_mode):
    first = client.post("/api/v1/demo/session")
    second = client.post("/api/v1/demo/session")
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()

def test_reset_preserves_non_demo_actor(client, session, demo_mode):
    ordinary = make_actor(session, external_reference="NOT-A-DEMO")
    client.delete("/api/v1/demo/session")
    assert session.get(Actor, ordinary.id) is not None
```

- [ ] **Step 2: Run the focused tests and observe missing settings/routes**

Run: `uv run --project backend pytest backend/tests/unit/test_config.py backend/tests/integration/test_demo_api.py -q`

Expected: FAIL because `demo_mode`, demo services, and routes do not exist.

- [ ] **Step 3: Implement a transaction-safe, namespaced demo service**

Use the reserved external-reference prefix `IMMIGRATIONFLOW-DEMO-V1:` and acquire a PostgreSQL transaction advisory lock before lookup/create. Return this exact response shape:

```python
class DemoSessionResponse(BaseModel):
    applicant_actor_id: UUID
    officer_actor_id: UUID
    case_id: UUID
    case_number: str
```

Reject both routes with `404` when `settings.demo_mode` is false. Reset only rows reachable from the reserved case and actors, inside one transaction, in foreign-key-safe order. Seed reviewed synthetic institution/programme/applicant values and metadata-only document records through existing domain services where available.

- [ ] **Step 4: Add concurrent idempotency and reset-isolation coverage**

Start two database sessions in the integration test, invoke `get_or_create` concurrently, and assert one reserved applicant, officer, and case. Insert an ordinary case before reset and assert it remains afterward.

- [ ] **Step 5: Run backend quality gates**

Run: `uv run --project backend pytest backend/tests/unit/test_config.py backend/tests/integration/test_demo_api.py -q`

Run: `uv run --project backend ruff check backend/app backend/tests`

Run: `uv run --project backend mypy backend/app`

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add .env.example backend/app backend/tests
git commit -m "feat: add safe synthetic demo sessions"
```

### Task 2: Actor-scoped demo read projections

**Files:**
- Create: `backend/app/domains/cases/queries.py`
- Modify: `backend/app/api/applicant.py`
- Modify: `backend/app/api/officer.py`
- Modify: `backend/app/api/schemas.py`
- Test: `backend/tests/integration/test_case_detail_api.py`

**Interfaces:**
- Consumes: existing actor dependency, case/checklist/evaluation/audit models, and Task 1 session identifiers.
- Produces: `GET /api/v1/applicant/cases/{id}`, `/timeline`, `/evaluation`; `GET /api/v1/officer/cases/{id}`; enriched officer queue summaries.

- [ ] **Step 1: Write failing applicant projection tests**

```python
def test_applicant_detail_is_owned_and_source_traceable(client, seeded_demo):
    response = client.get(
        f"/api/v1/applicant/cases/{seeded_demo.case_id}",
        headers={"X-Actor-Id": str(seeded_demo.applicant_actor_id)},
    )
    assert response.status_code == 200
    assert response.json()["synthetic"] is True
    assert response.json()["institution"]["name"]

def test_applicant_cannot_read_another_case(client, other_case, applicant_headers):
    assert client.get(f"/api/v1/applicant/cases/{other_case.id}", headers=applicant_headers).status_code == 403
```

- [ ] **Step 2: Write failing timeline, evaluation, and officer tests**

Assert chronological `(occurred_at, id)` ordering, source URL/review metadata on material requirements, current plus superseded evaluation identifiers, officer-only access, valid empty findings, and enriched queue summaries.

- [ ] **Step 3: Run the focused integration test**

Run: `uv run --project backend pytest backend/tests/integration/test_case_detail_api.py -q`

Expected: FAIL with missing routes and schemas.

- [ ] **Step 4: Implement focused read-query functions**

Define immutable projection dataclasses in `queries.py` and have routes translate them into Pydantic responses. Use eager, bounded SQLAlchemy selects; never serialize ORM objects lazily after the session boundary. Preserve `{ "detail": "..." }` errors and existing actor checks.

- [ ] **Step 5: Run projection and regression suites**

Run: `uv run --project backend pytest backend/tests/integration/test_case_detail_api.py backend/tests/integration/test_case_api.py -q`

Run: `uv run --project backend ruff check backend/app backend/tests && uv run --project backend mypy backend/app`

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app backend/tests/integration/test_case_detail_api.py
git commit -m "feat: expose portfolio case projections"
```

### Task 3: Frontend foundation and validated API boundary

**Files:**
- Delete: `apps/applicant-web/.gitkeep`
- Delete: `apps/officer-dashboard/.gitkeep`
- Create: `apps/immigration-flow-web/package.json`
- Create: `apps/immigration-flow-web/package-lock.json`
- Create: `apps/immigration-flow-web/tsconfig.json`
- Create: `apps/immigration-flow-web/vite.config.ts`
- Create: `apps/immigration-flow-web/eslint.config.js`
- Create: `apps/immigration-flow-web/index.html`
- Create: `apps/immigration-flow-web/src/main.tsx`
- Create: `apps/immigration-flow-web/src/app/App.tsx`
- Create: `apps/immigration-flow-web/src/app/router.tsx`
- Create: `apps/immigration-flow-web/src/app/queryClient.ts`
- Create: `apps/immigration-flow-web/src/api/client.ts`
- Create: `apps/immigration-flow-web/src/api/schemas.ts`
- Create: `apps/immigration-flow-web/src/styles/tokens.css`
- Create: `apps/immigration-flow-web/src/styles/global.css`
- Test: `apps/immigration-flow-web/src/api/client.test.ts`
- Test: `apps/immigration-flow-web/src/app/App.test.tsx`

**Interfaces:**
- Consumes: Task 1 and Task 2 JSON contracts.
- Produces: `apiRequest<T>(path, schema, options)`, `ApiError`, `DataIntegrityError`, application router, query client, and shared design tokens.

- [ ] **Step 1: Scaffold exact dependencies and scripts**

Use scripts `dev`, `build`, `lint`, `typecheck`, `test`, `test:coverage`, and `e2e`. Pin supported major versions and commit the lockfile; configure Vite `/api` proxy to `http://127.0.0.1:8000`.

- [ ] **Step 2: Write failing API-boundary tests**

```ts
it("rejects a malformed successful response", async () => {
  server.use(http.get("/api/example", () => HttpResponse.json({ id: 12 })));
  await expect(apiRequest("/api/example", z.object({ id: z.string() })))
    .rejects.toBeInstanceOf(DataIntegrityError);
});

it("preserves conflict status and safe detail", async () => {
  server.use(http.post("/api/example", () => HttpResponse.json({ detail: "Case changed" }, { status: 409 })));
  await expect(apiRequest("/api/example", z.unknown(), { method: "POST" }))
    .rejects.toMatchObject({ status: 409, detail: "Case changed" });
});
```

- [ ] **Step 3: Implement transport, schemas, router, and accessible shell**

The transport sends `X-Actor-Id` only when explicitly supplied, parses every success with Zod, maps non-JSON errors to generic messages, and never logs response bodies. The shell includes skip navigation, semantic landmarks, demo banner, and not-found page.

- [ ] **Step 4: Verify frontend foundation**

Run: `npm --prefix apps/immigration-flow-web run lint`

Run: `npm --prefix apps/immigration-flow-web run typecheck`

Run: `npm --prefix apps/immigration-flow-web test -- --run`

Run: `npm --prefix apps/immigration-flow-web run build`

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add apps
git commit -m "feat: establish portfolio web foundation"
```

### Task 4: Landing page and recoverable demo-session state

**Files:**
- Create: `apps/immigration-flow-web/src/features/demo/api.ts`
- Create: `apps/immigration-flow-web/src/features/demo/session.ts`
- Create: `apps/immigration-flow-web/src/features/demo/LandingPage.tsx`
- Create: `apps/immigration-flow-web/src/features/demo/LandingPage.module.css`
- Create: `apps/immigration-flow-web/src/components/AsyncBoundary.tsx`
- Modify: `apps/immigration-flow-web/src/app/router.tsx`
- Test: `apps/immigration-flow-web/src/features/demo/LandingPage.test.tsx`
- Test: `apps/immigration-flow-web/src/features/demo/session.test.ts`

**Interfaces:**
- Consumes: `DemoSessionResponse` and `apiRequest` from Tasks 1 and 3.
- Produces: `useDemoSession()`, `resetDemoSession()`, landing navigation for both roles, and shared unavailable/retry states.

- [ ] **Step 1: Write failing session recovery tests**

Assert initial bootstrap, valid local-storage restoration, stale case `404` followed by one re-bootstrap, wrong-role `403` clearing session, reset confirmation, reset failure retaining the current session, and reserved-key-only local storage.

- [ ] **Step 2: Write failing accessible landing-page tests**

Assert one `main` landmark, independent-prototype disclaimer, synthetic-data label, Applicant and Officer links, keyboard-operable reset confirmation, loading announcement, and service-unavailable retry.

- [ ] **Step 3: Implement demo state and landing experience**

Use one versioned storage key `immigration-flow.demo.v1`, TanStack Query for bootstrap/reset, and CSS tokens from Task 3. Do not place API URLs, secrets, names, or document metadata in storage.

- [ ] **Step 4: Run frontend tests and build**

Run: `npm --prefix apps/immigration-flow-web test -- --run src/features/demo`

Run: `npm --prefix apps/immigration-flow-web run lint && npm --prefix apps/immigration-flow-web run typecheck && npm --prefix apps/immigration-flow-web run build`

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add apps/immigration-flow-web
git commit -m "feat: add recoverable portfolio demo entry"
```

### Task 5: Applicant preparation and handover workspace

**Files:**
- Create: `apps/immigration-flow-web/src/features/applicant/api.ts`
- Create: `apps/immigration-flow-web/src/features/applicant/ApplicantLayout.tsx`
- Create: `apps/immigration-flow-web/src/features/applicant/CaseOverview.tsx`
- Create: `apps/immigration-flow-web/src/features/applicant/RequirementsPage.tsx`
- Create: `apps/immigration-flow-web/src/features/applicant/EvaluationPage.tsx`
- Create: `apps/immigration-flow-web/src/features/applicant/HandoverPage.tsx`
- Create: `apps/immigration-flow-web/src/features/applicant/Applicant.module.css`
- Modify: `apps/immigration-flow-web/src/app/router.tsx`
- Test: `apps/immigration-flow-web/src/features/applicant/ApplicantWorkflow.test.tsx`

**Interfaces:**
- Consumes: Task 2 applicant projections, existing checklist/submission endpoints, Task 3 API client, Task 4 session.
- Produces: applicant routes and query/mutation hooks keyed by case ID and applicant actor ID.

- [ ] **Step 1: Write failing overview and requirements tests**

Assert case/institution/programme rendering, synthetic label, status text plus icon, rule-set version, official-source link/review date, metadata-only wording, phone-width semantics, and empty or unavailable checklist recovery.

- [ ] **Step 2: Write failing evaluation and handover tests**

Assert “readiness result” wording, no approval prediction, findings readable without color, explicit submission timestamp explanation, confirmation before mutation, disabled handover outside `DRAFT`, and a `409` causing refetch plus state-changed message.

- [ ] **Step 3: Implement applicant pages and API hooks**

Use nested routes under `/applicant/cases/:caseId`; mutations invalidate detail, checklist, evaluation, and timeline keys. External official-source links display their host and open with safe `rel` attributes.

- [ ] **Step 4: Verify Applicant workspace**

Run: `npm --prefix apps/immigration-flow-web test -- --run src/features/applicant`

Run: `npm --prefix apps/immigration-flow-web run lint && npm --prefix apps/immigration-flow-web run typecheck && npm --prefix apps/immigration-flow-web run build`

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add apps/immigration-flow-web
git commit -m "feat: build applicant preparation workspace"
```

### Task 6: Officer queue, review, and audit workspace

**Files:**
- Create: `apps/immigration-flow-web/src/features/officer/api.ts`
- Create: `apps/immigration-flow-web/src/features/officer/OfficerLayout.tsx`
- Create: `apps/immigration-flow-web/src/features/officer/OfficerQueue.tsx`
- Create: `apps/immigration-flow-web/src/features/officer/OfficerCasePage.tsx`
- Create: `apps/immigration-flow-web/src/features/officer/AuditTimeline.tsx`
- Create: `apps/immigration-flow-web/src/features/officer/Officer.module.css`
- Modify: `apps/immigration-flow-web/src/app/router.tsx`
- Test: `apps/immigration-flow-web/src/features/officer/OfficerWorkflow.test.tsx`

**Interfaces:**
- Consumes: Task 2 officer projections, existing start-processing endpoint, Task 3 client, Task 4 session.
- Produces: `/officer/cases`, `/officer/cases/:caseId`, queue/detail hooks, audit timeline, and processing mutation.

- [ ] **Step 1: Write failing queue tests**

Assert submitted and in-process filters, chronological rows, readiness summary, valid empty state, loading/error announcements, and labelled card markup used when the table presentation collapses.

- [ ] **Step 2: Write failing case and transition tests**

Assert checklist/finding/source rendering, append-only evaluation history, chronological audit entries, processing available only for `SUBMITTED`, success invalidating queue/detail, and `409` refetching current state with explanation.

- [ ] **Step 3: Implement officer pages and hooks**

Keep evidence compact but human-readable. Do not expose raw audit payloads, internal storage references, document hashes, database identifiers unrelated to the reviewer, or approve/reject controls.

- [ ] **Step 4: Verify Officer workspace**

Run: `npm --prefix apps/immigration-flow-web test -- --run src/features/officer`

Run: `npm --prefix apps/immigration-flow-web run lint && npm --prefix apps/immigration-flow-web run typecheck && npm --prefix apps/immigration-flow-web run build`

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add apps/immigration-flow-web
git commit -m "feat: build officer review workspace"
```

### Task 7: Cross-role browser smoke path and local launcher

**Files:**
- Create: `apps/immigration-flow-web/playwright.config.ts`
- Create: `apps/immigration-flow-web/e2e/student-pass-demo.spec.ts`
- Create: `Makefile`
- Create: `scripts/run_demo.sh`
- Modify: `docker-compose.yml`
- Modify: `.gitignore`
- Test: `apps/immigration-flow-web/e2e/student-pass-demo.spec.ts`

**Interfaces:**
- Consumes: all prior API and UI tasks.
- Produces: `make demo`, `make demo-stop`, `make test`, and a Playwright full-workflow smoke test.

- [ ] **Step 1: Write the browser test before launcher completion**

```ts
test("synthetic case moves from applicant handover to officer processing", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: /explore as applicant/i }).click();
  await page.getByRole("link", { name: /requirements/i }).click();
  await expect(page.getByText(/official source/i)).toBeVisible();
  await page.getByRole("link", { name: /handover/i }).click();
  await page.getByRole("button", { name: /submit to immigration/i }).click();
  await page.getByRole("button", { name: /confirm handover/i }).click();
  await page.getByRole("link", { name: /officer workspace/i }).click();
  await page.getByRole("link", { name: /case/i }).first().click();
  await page.getByRole("button", { name: /start processing/i }).click();
  await expect(page.getByText(/in process/i)).toBeVisible();
});
```

- [ ] **Step 2: Implement deterministic launcher and shutdown**

`scripts/run_demo.sh` must verify Docker, start PostgreSQL, run `alembic upgrade head`, export `DEMO_MODE=true`, and run backend/frontend processes with a trap that stops child processes. It must never print database credentials. `make demo-stop` stops only project demo containers/process metadata, not unrelated Docker resources.

- [ ] **Step 3: Run the complete local browser path**

Run: `npm --prefix apps/immigration-flow-web run e2e`

Expected: one cross-role scenario passes on Chromium.

- [ ] **Step 4: Run all local gates**

Run: `make test`

Expected: backend, migrations, knowledge validation, frontend lint/type/unit/build, and e2e pass.

- [ ] **Step 5: Commit**

```bash
git add Makefile scripts docker-compose.yml .gitignore apps/immigration-flow-web
git commit -m "test: verify complete portfolio demo journey"
```

### Task 8: CI, portfolio documentation, and final evidence

**Files:**
- Create: `.github/workflows/portfolio-demo-ci.yml`
- Modify: `README.md`
- Modify: `backend/README.md`
- Modify: `docs/PROJECT_SCOPE.md`
- Create: `docs/DEMO_GUIDE.md`
- Create: `docs/architecture/PHASE_3_PORTFOLIO_DEMO.md`
- Create: `docs/assets/demo/.gitkeep`

**Interfaces:**
- Consumes: the runnable demo and commands from Task 7.
- Produces: CI enforcement, reviewer setup guide, architecture summary, production-gap record, and screenshot location.

- [ ] **Step 1: Add CI with PostgreSQL and browser dependencies**

Run backend lint/type/tests/migration/knowledge validation and frontend lint/type/tests/build in separate jobs; run Playwright only after both succeed. Upload Playwright traces only on failure and retain them for seven days.

- [ ] **Step 2: Write the reviewer-facing demo guide**

Document prerequisites, `make demo`, the exact Applicant-to-Officer walkthrough, demo reset, test commands, troubleshooting, synthetic-data boundary, and the disclaimer. Record why the portfolio version is local rather than always-on and enumerate production requirements: real authentication, authorization review, managed PostgreSQL, encrypted object storage, secrets management, monitoring, retention, backups, and scheduled official-source monitoring.

- [ ] **Step 3: Update status and remove stale milestone language**

Update the root README repository map to the unified web app, replace the old “next milestone” statement, and mark Student Pass V1 browser demo as delivered without claiming Graduate Pass or broader Immigration coverage.

- [ ] **Step 4: Capture final screenshots after verification**

Capture landing, Applicant requirements, Applicant readiness, Officer queue, and Officer case timeline at desktop width plus one Applicant mobile view. Store optimized images under `docs/assets/demo/` with descriptive filenames and alt text in `README.md`.

- [ ] **Step 5: Run final verification from a clean state**

Run: `git status --short`

Run: `make test`

Run: `ruby scripts/validate_knowledge_base.rb`

Expected: clean pre-test tree, all checks pass, and validation reports the current source/requirement/rule/case counts.

- [ ] **Step 6: Commit**

```bash
git add .github README.md backend/README.md docs
git commit -m "docs: deliver Student Pass portfolio demo"
```

### Task 9: Branch-level review and pull request

**Files:**
- Review: all changes since `main`
- Modify: only files needed to resolve verified review findings

**Interfaces:**
- Consumes: Tasks 1–8.
- Produces: one review-ready branch and a PR against `main`.

- [ ] **Step 1: Inspect the complete diff and history**

Run: `git diff --check main...HEAD`

Run: `git diff --stat main...HEAD`

Run: `git log --oneline main..HEAD`

Expected: no whitespace errors; commits align with the planned slices.

- [ ] **Step 2: Run fresh full verification**

Run: `make test`

Expected: all backend, frontend, migration, knowledge, and e2e checks pass in the final tree.

- [ ] **Step 3: Review security and product boundaries**

Search for credentials, non-synthetic names/data, official-approval wording, unguarded demo routes, raw audit payload display, external links without safe attributes, and browser storage beyond the approved identifiers. Resolve every concrete finding and rerun affected tests.

- [ ] **Step 4: Push and open the PR**

```bash
git push -u origin codex/phase-3-portfolio-demo
```

Create a PR summarizing the product workflow, safety boundaries, screenshots, verification counts, and local demo command. Do not merge until the user explicitly confirms the final PR.
