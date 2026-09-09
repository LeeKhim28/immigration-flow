# Phase 2B.2A Knowledge Sync and Activation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an auditable Student Pass V1 pipeline that monitors reviewed official sources, synchronizes immutable Git-reviewed knowledge into PostgreSQL, requires administrator approval, and activates approved rule releases safely at their effective time.

**Architecture:** Extend the synchronous FastAPI modular monolith with an isolated `app.knowledge` application layer and a `domains.knowledge` persistence model. GitHub remains the canonical authoring/review source; monitor adapters can report changes but cannot publish rules, while atomic sync and activation services enforce provenance, immutability, governance, and time boundaries in PostgreSQL.

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy 2.0, Alembic, Psycopg 3, PostgreSQL 18, httpx, Beautiful Soup 4, PyYAML, jsonschema, argparse, pytest, Ruff, mypy, Ruby knowledge validators, GitHub Actions

**Spec:** `docs/superpowers/specs/2026-09-02-phase-2b-2a-knowledge-sync-activation-design.md`

## Global Constraints

- Implement only Phase 2B.2A. Do not add case rule assignment, case evaluation, re-evaluation, case requirements, case tasks, case deadlines, Applicant APIs, Institution APIs, or Officer APIs.
- GitHub is canonical authoring history; PostgreSQL is runtime version and governance history.
- A detected webpage change never edits a requirement, rule, baseline, or active database version.
- Monitor only explicitly enabled, reviewed Student Pass V1 sources over approved HTTPS hosts.
- Monitor outcomes are exactly `UNCHANGED`, `CHANGED`, and `BLOCKED`; do not add `FETCH_FAILED`.
- One successful comparable check resets the failure streak; the third consecutive scheduled failure produces `BLOCKED`.
- Do not store complete official webpages, secrets, cookies, real applicant data, passport bytes, or evidence files.
- Synchronization requires a clean checkout and an explicit Git SHA equal to `HEAD`.
- Synchronization is atomic and idempotent; formal imported rows and the `SUCCEEDED` transition commit together.
- Immutable revisions, versions, provenance links, approvals, and audits are enforced at the PostgreSQL boundary.
- Only an `ADMINISTRATOR` actor may approve or reject a rule-set version. `SYSTEM` may synchronize and activate but cannot approve.
- Persisted rule-set statuses remain `DRAFT`, `REVIEW`, `ACTIVE`, and `RETIRED`. `SCHEDULED` is derived, never stored.
- Interpret an official time in its stated timezone; otherwise use `Asia/Kuala_Lumpur`, then store the resolved instant as `timestamptz`.
- Activation is locked, atomic, and failure-safe. It never creates case assignments in this phase.
- Rule documents use a bounded allowlisted DSL. Never use Python `eval`, `exec`, shell evaluation, dynamic imports, or a general-purpose template engine.
- Keep the existing `/health` and `/health/database` endpoints only.
- Python remains `>=3.14,<3.15`; PostgreSQL remains on supported 18.x; schema changes use Alembic only.
- Every task uses synthetic fixtures, follows red-green-refactor, passes focused tests, and ends with an independently reviewable commit.

---

## Planned file structure

```text
immigration-flow/
├── .github/workflows/
│   ├── backend-ci.yml
│   └── source-monitor.yml
├── data/official-sources/
│   ├── monitoring-baseline.schema.json
│   └── monitoring-baselines.yaml
├── docs/superpowers/specs/
│   └── 2026-09-02-phase-2b-2a-knowledge-sync-activation-design.md
├── scripts/
│   └── validate_knowledge_base.rb
└── backend/
    ├── pyproject.toml
    ├── uv.lock
    ├── app/
    │   ├── core/config.py
    │   ├── main.py
    │   ├── database/
    │   │   ├── enums.py
    │   │   └── models.py
    │   ├── domains/knowledge/
    │   │   ├── __init__.py
    │   │   └── models.py
    │   └── knowledge/
    │       ├── __init__.py
    │       ├── activation.py
    │       ├── cli.py
    │       ├── contracts.py
    │       ├── dsl.py
    │       ├── fingerprints.py
    │       ├── github_issues.py
    │       ├── monitor.py
    │       ├── normalization.py
    │       ├── repository.py
    │       ├── scheduler.py
    │       ├── sync.py
    │       └── url_safety.py
    ├── migrations/versions/
    │   ├── 0005_knowledge_sources_and_requirements.py
    │   └── 0006_rule_versions_and_activation.py
    └── tests/
        ├── fixtures/knowledge/
        │   ├── changed.html
        │   ├── layout-only-change.html
        │   ├── original.html
        │   └── synthetic_repository/
        ├── integration/
        │   ├── test_activation_schema.py
        │   ├── test_knowledge_schema.py
        │   ├── test_knowledge_sync.py
        │   └── test_rule_governance_schema.py
        ├── migration/test_migration_round_trip.py
        └── unit/knowledge/
            ├── test_activation.py
            ├── test_dsl.py
            ├── test_fingerprints.py
            ├── test_github_issues.py
            ├── test_monitor.py
            ├── test_normalization.py
            ├── test_repository.py
            └── test_url_safety.py
```

`domains.knowledge.models` owns only SQLAlchemy mappings. `app.knowledge` owns orchestration and replaceable adapters. Migrations own cross-row constraints, immutable-history triggers, and audit constraints. CLI code parses arguments and delegates; it contains no policy logic.

---

### Task 1: Knowledge contracts and runtime dependencies

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/uv.lock`
- Create: `backend/app/knowledge/__init__.py`
- Create: `backend/app/knowledge/contracts.py`
- Create: `backend/tests/unit/knowledge/test_contracts.py`

**Interfaces:**
- Produces: `MonitorOutcome`, `MonitorTrigger`, `CheckError`, `MonitorBaseline`, `MonitorState`, `RetrievedSource`, `MonitorResult`, `IssueDraft`
- Produces: JSON-safe `MonitorState.to_dict()` and `MonitorState.from_dict()`
- Consumes: existing Python 3.14 backend runtime

- [ ] **Step 1: Write failing contract serialization tests**

```python
from app.knowledge.contracts import MonitorOutcome, MonitorState


def test_monitor_outcomes_exclude_fetch_failed() -> None:
    assert {item.value for item in MonitorOutcome} == {
        "UNCHANGED",
        "CHANGED",
        "BLOCKED",
    }


def test_monitor_state_round_trips_json_data() -> None:
    state = MonitorState(
        source_id="MY-TEST-SOURCE",
        last_outcome=MonitorOutcome.UNCHANGED,
        consecutive_failures=2,
        last_comparable_hash="a" * 64,
    )
    assert MonitorState.from_dict(state.to_dict()) == state
```

- [ ] **Step 2: Run the focused test and verify RED**

```bash
cd backend
uv run pytest tests/unit/knowledge/test_contracts.py -v
```

Expected: FAIL because `app.knowledge.contracts` does not exist.

- [ ] **Step 3: Add production parsing and retrieval dependencies**

Move `httpx>=0.28,<1` from the dev group to project dependencies and add:

```toml
"beautifulsoup4>=4.13,<5",
"jsonschema>=4.25,<5",
"pyyaml>=6.0,<7",
```

Add `types-beautifulsoup4` and `types-PyYAML` to the dev group, run `uv lock`, and retain the compatible locked versions selected by uv.

- [ ] **Step 4: Implement immutable typed contracts**

Use frozen dataclasses and `StrEnum`. Define the exact contract fields as follows:

```text
CheckError(code, public_message, checked_at)
MonitorBaseline(source_id, canonical_url, allowed_hosts, selector, strategy_version, approved_hash, captured_at, git_commit_sha)
MonitorState(source_id, last_outcome, consecutive_failures, last_comparable_hash)
RetrievedSource(final_url, retrieved_at, normalized_content, content_hash)
MonitorResult(source_id, outcome, previous_hash, current_hash, change_summary, error, next_state, should_notify)
IssueDraft(title, body, labels, dedupe_marker)
```

`MonitorState.from_dict()` must reject negative failure counts, unknown outcomes, non-string source IDs, and non-hex hashes. `CheckError` contains only a stable code, a bounded public message, and a timezone-aware check time; it must not accept response bodies or headers.

```python
class MonitorOutcome(StrEnum):
    UNCHANGED = "UNCHANGED"
    CHANGED = "CHANGED"
    BLOCKED = "BLOCKED"


class MonitorTrigger(StrEnum):
    SCHEDULED = "SCHEDULED"
    MANUAL = "MANUAL"


@dataclass(frozen=True, slots=True)
class MonitorState:
    source_id: str
    last_outcome: MonitorOutcome
    consecutive_failures: int
    last_comparable_hash: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "source_id": self.source_id,
            "last_outcome": self.last_outcome.value,
            "consecutive_failures": self.consecutive_failures,
            "last_comparable_hash": self.last_comparable_hash,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "MonitorState":
        source_id = value.get("source_id")
        failures = value.get("consecutive_failures")
        content_hash = value.get("last_comparable_hash")
        if not isinstance(source_id, str) or not source_id:
            raise ValueError("source_id must be a non-empty string")
        if not isinstance(failures, int) or isinstance(failures, bool) or failures < 0:
            raise ValueError("consecutive_failures must be a non-negative integer")
        if content_hash is not None and (
            not isinstance(content_hash, str)
            or re.fullmatch(r"[0-9a-f]{64}", content_hash) is None
        ):
            raise ValueError("last_comparable_hash must be lowercase SHA-256")
        return cls(
            source_id=source_id,
            last_outcome=MonitorOutcome(str(value.get("last_outcome"))),
            consecutive_failures=failures,
            last_comparable_hash=content_hash,
        )
```

- [ ] **Step 5: Run quality and focused tests**

```bash
uv run ruff check app/knowledge tests/unit/knowledge/test_contracts.py
uv run ruff format --check app/knowledge tests/unit/knowledge/test_contracts.py
uv run mypy app
uv run pytest tests/unit/knowledge/test_contracts.py -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock backend/app/knowledge backend/tests/unit/knowledge/test_contracts.py
git commit -m "build: add knowledge monitoring contracts"
```

---

### Task 2: Safe source retrieval and deterministic normalization

**Files:**
- Create: `backend/app/knowledge/url_safety.py`
- Create: `backend/app/knowledge/normalization.py`
- Create: `backend/tests/unit/knowledge/test_url_safety.py`
- Create: `backend/tests/unit/knowledge/test_normalization.py`
- Create: `backend/tests/fixtures/knowledge/original.html`
- Create: `backend/tests/fixtures/knowledge/layout-only-change.html`
- Create: `backend/tests/fixtures/knowledge/changed.html`

**Interfaces:**
- Produces: `validate_public_https_url(url: str, allowed_hosts: frozenset[str], resolver: HostResolver) -> None`
- Produces: `normalize_html(document: bytes, selector: str | None, strategy_version: int) -> bytes`
- Produces: `content_sha256(normalized: bytes) -> str`
- Produces: `retrieve_source(config: MonitorBaseline, client: httpx.Client, resolver: HostResolver) -> RetrievedSource`
- Consumes: Task 1 contracts

- [ ] **Step 1: Write failing URL-safety tests**

Test exact rejection of HTTP, embedded credentials, unapproved hosts, loopback, RFC1918, link-local, IPv6 local addresses, oversized redirects, and redirects to a newly resolved private address. Test an approved host resolving only to public addresses.

```python
def test_rejects_redirect_to_private_address() -> None:
    resolver = FakeResolver({"official.example": ["203.0.113.8"], "internal": ["127.0.0.1"]})
    with pytest.raises(UnsafeSourceUrl, match="non-public destination"):
        validate_public_https_url("https://internal/policy", frozenset({"internal"}), resolver)
```

- [ ] **Step 2: Write failing normalization tests**

Assert the original and layout-only fixture produce the same bytes/hash, while the material policy-text fixture produces a different hash. Assert a missing configured selector fails closed.

- [ ] **Step 3: Run the tests and verify RED**

```bash
cd backend
uv run pytest tests/unit/knowledge/test_url_safety.py tests/unit/knowledge/test_normalization.py -v
```

Expected: FAIL because safety and normalization modules do not exist.

- [ ] **Step 4: Implement URL validation and manual redirect handling**

`HostResolver` is a protocol returning resolved IP strings. Reject any address for which `ipaddress.ip_address(value).is_global` is false. Disable httpx automatic redirects, validate every `Location`, allow at most three redirects, use a 15-second total timeout, accept at most 5 MiB, and send `ImmigrationFlow-SourceMonitor/1.0 (+repository URL)` as the user agent. Never forward authorization or cookies.

- [ ] **Step 5: Implement deterministic HTML normalization**

Parse with Beautiful Soup, select the configured region when present, remove `script`, `style`, `nav`, `noscript`, `template`, comments, and elements marked as cookie/consent banners, normalize Unicode to NFC, collapse whitespace, and encode UTF-8. Reject unknown strategy versions and empty normalized content.

- [ ] **Step 6: Run focused and static verification**

```bash
uv run pytest tests/unit/knowledge/test_url_safety.py tests/unit/knowledge/test_normalization.py -v
uv run ruff check app/knowledge tests/unit/knowledge
uv run ruff format --check app/knowledge tests/unit/knowledge
uv run mypy app
```

Expected: all pass without network access.

- [ ] **Step 7: Commit**

```bash
git add backend/app/knowledge backend/tests/unit/knowledge backend/tests/fixtures/knowledge
git commit -m "feat: add safe official source retrieval"
```

---

### Task 3: Monitoring state machine and report generation

**Files:**
- Create: `backend/app/knowledge/monitor.py`
- Create: `backend/tests/unit/knowledge/test_monitor.py`

**Interfaces:**
- Produces: `check_source(baseline, prior_state, trigger, retrieve, now) -> MonitorResult`
- Produces: `build_change_summary(previous: bytes, current: bytes, max_chars: int = 2000) -> str`
- Consumes: Task 1 contracts and Task 2 retrieval/normalization

- [ ] **Step 1: Write the failing state-transition table tests**

Cover these exact transitions:

```text
success + equal hash       -> UNCHANGED, streak 0
success + different hash   -> CHANGED, streak 0
scheduled failure #1       -> retain prior outcome, streak 1
scheduled failure #2       -> retain prior outcome, streak 2
scheduled failure #3       -> BLOCKED, streak 3
manual failure             -> retain prior outcome and streak
success after failures     -> comparable outcome, streak 0
```

Also prove the bounded summary contains changed public text, excludes removed script/cookie text, and truncates at 2,000 characters.

- [ ] **Step 2: Run focused tests and verify RED**

```bash
cd backend
uv run pytest tests/unit/knowledge/test_monitor.py -v
```

Expected: FAIL because `check_source` and `build_change_summary` do not exist.

- [ ] **Step 3: Implement the pure state machine**

The retrieval callable returns `RetrievedSource` or raises a typed public monitor error. Catch only typed retrieval/normalization errors; unexpected programming errors must fail the run. Do not create a fourth outcome. Manual checks report errors but do not advance the scheduled-failure streak.

- [ ] **Step 4: Verify focused and regression unit tests**

```bash
uv run pytest tests/unit/knowledge -v
uv run ruff check app/knowledge tests/unit/knowledge
uv run ruff format --check app/knowledge tests/unit/knowledge
uv run mypy app
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/knowledge/monitor.py backend/tests/unit/knowledge/test_monitor.py
git commit -m "feat: classify official source monitor results"
```

---

### Task 4: Repository baselines, GitHub Issue gateway, and monitor CLI

**Files:**
- Create: `data/official-sources/monitoring-baseline.schema.json`
- Create: `backend/app/knowledge/repository.py`
- Create: `backend/app/knowledge/github_issues.py`
- Create: `backend/app/knowledge/cli.py`
- Create: `backend/tests/unit/knowledge/test_repository.py`
- Create: `backend/tests/unit/knowledge/test_github_issues.py`
- Modify: `scripts/validate_knowledge_base.rb`

**Interfaces:**
- Produces: `load_monitor_baselines(root: Path) -> Sequence[MonitorBaseline]`
- Produces: `ReviewIssueGateway.ensure_labels() -> None`
- Produces: `ReviewIssueGateway.upsert(result: MonitorResult) -> None`
- Produces: `GitHubIssueGateway(repo: str, token: str, client: httpx.Client)`
- Produces: `CollectingIssueGateway`, an in-memory no-network adapter used by dry-run and tests
- Produces CLI: `python -m app.knowledge.cli monitor --root PATH --state PATH --output-state PATH --trigger scheduled|manual [--dry-run]`
- Produces CLI: `python -m app.knowledge.cli bootstrap-baselines --root PATH --output PATH`
- Consumes: Tasks 1–3

- [ ] **Step 1: Write failing schema and repository-loader tests**

The schema requires `schema_version: 1`, unique source IDs, HTTPS URLs, allowlisted hosts, `strategy_version: 1`, optional CSS selector, a 64-character lowercase SHA-256 hash, capture timestamp, and 40- or 64-character lowercase Git SHA. The loader rejects unknown source IDs, sources not marked `reviewed`, and duplicate IDs.

- [ ] **Step 2: Write failing Issue-gateway tests**

Use `httpx.MockTransport` to prove the gateway creates the three required repository labels only when missing, searches for the hidden marker `<!-- immigration-flow-source:SOURCE_ID -->`, updates one matching open issue, creates only when none exists, and sends only title/body/labels. Prove `CollectingIssueGateway` records intended operations without making HTTP requests. Assert no token, cookie, response body, or full normalized document appears in the request.

- [ ] **Step 3: Run focused tests and verify RED**

```bash
cd backend
uv run pytest tests/unit/knowledge/test_repository.py tests/unit/knowledge/test_github_issues.py -v
```

Expected: FAIL because the loader, gateway, and baseline schema do not exist.

- [ ] **Step 4: Implement repository loading and extend the Ruby validator**

The Ruby validator must parse the new JSON schema as JSON and, when `monitoring-baselines.yaml` exists, verify unique IDs, registered reviewed sources, exact canonical URLs, lowercase hashes, and the eight initially referenced Student Pass V1 source IDs. It must not fetch the network.

- [ ] **Step 5: Implement deduplicated Issue operations and CLI adapters**

Use GitHub REST endpoints only under `https://api.github.com/repos/{owner}/{repo}`. `ensure_labels()` idempotently creates missing labels named `source-monitor`, `source-changed`, and `source-blocked` before issue upserts. The stable hidden marker is the only deduplication key. The CLI reads prior state, runs each enabled source once, upserts issues only for `CHANGED` or `BLOCKED`, and atomically replaces the output state file using a temporary sibling plus `os.replace`. With `--dry-run`, the CLI uses `CollectingIssueGateway`, prints only sanitized intended operations, requires no GitHub token, and never contacts the GitHub API.

- [ ] **Step 6: Verify CLI help, tests, and static checks**

```bash
uv run python -m app.knowledge.cli --help
uv run pytest tests/unit/knowledge -v
uv run ruff check app/knowledge tests/unit/knowledge
uv run ruff format --check app/knowledge tests/unit/knowledge
uv run mypy app
cd ..
ruby scripts/validate_knowledge_base.rb
```

Expected: all pass; the validator continues to report 13 sources, 17 requirements, 16 rules, and 12 cases before the production baseline file is added.

- [ ] **Step 7: Commit**

```bash
git add data/official-sources/monitoring-baseline.schema.json scripts/validate_knowledge_base.rb backend/app/knowledge backend/tests/unit/knowledge
git commit -m "feat: add source monitoring repository contract"
```

---

### Task 5: Approved monitoring baselines and scheduled workflow

**Files:**
- Create: `data/official-sources/monitoring-baselines.yaml`
- Create: `.github/workflows/source-monitor.yml`
- Modify: `backend/tests/unit/knowledge/test_repository.py`
- Modify: `data/official-sources/README.md`

**Interfaces:**
- Produces: reviewed baseline records for exactly the eight Student Pass V1 sources referenced by current requirements/rules
- Produces: daily schedule and `workflow_dispatch` monitor entry points
- Consumes: Task 4 CLI and schema

- [ ] **Step 1: Write failing production-baseline assertions**

Assert the production file loads exactly these source IDs:

```python
EXPECTED = {
    "MY-EMGS-INSURANCE-2026",
    "MY-EMGS-MEDICAL-SCREENING",
    "MY-EMGS-PASSPORT-PHOTO-GUIDELINES",
    "MY-EMGS-SEV-REQUIRED-COUNTRIES",
    "MY-EMGS-STUDENT-PASS-REQUIRED-DOCUMENTS",
    "MY-IMMIGRATION-STUDENT-PASS",
    "MY-IMMIGRATION-VISA-REQUIREMENTS-BY-COUNTRY",
    "MY-MQA-MQR-SEARCH",
}
```

Expected initial result: FAIL because `monitoring-baselines.yaml` does not exist.

- [ ] **Step 2: Generate a candidate baseline without editing canonical data**

```bash
cd backend
uv run python -m app.knowledge.cli bootstrap-baselines --root .. --output ../.monitoring-baselines.candidate.yaml
```

Review every URL, selector, normalized-content sample, hash, and retrieval error. Do not accept CAPTCHA, authentication, private redirects, empty content, or a source whose retrieved material does not match its registered title. Resolve blocked sources through a documented manual monitoring mode rather than weakening URL safety.

- [ ] **Step 3: Approve the actual observed hashes**

After human review, move only the reviewed records into `data/official-sources/monitoring-baselines.yaml`, set `captured_at` to the actual UTC retrieval instant and `git_commit_sha` to the pre-baseline `HEAD`, then delete the candidate file. No invented hash or placeholder value is allowed.

- [ ] **Step 4: Add the scheduled workflow**

Configure daily execution at `18:30 UTC` (02:30 Malaysia time on the following calendar day) and manual dispatch. Set:

```yaml
permissions:
  contents: read
  actions: read
  issues: write
```

The job checks out the repository, installs locked Python 3.14 dependencies, downloads the `source-monitor-state` artifact from the most recent completed source-monitor run with `gh run download` when available, runs the monitor CLI, and uploads the sanitized next state as `source-monitor-state` with `actions/upload-artifact@v4` and 30-day retention. Absence of a prior artifact starts an empty streak; CLI or workflow defects fail the job.

- [ ] **Step 5: Run offline validation and one explicitly authorized manual monitor run**

```bash
ruby scripts/validate_knowledge_base.rb
cd backend
uv run pytest tests/unit/knowledge -v
uv run python -m app.knowledge.cli monitor --root .. --state ../.empty-monitor-state.json --output-state ../.next-monitor-state.json --trigger manual --dry-run
```

The live source retrieval requires network permission. Inspect its public-only output and remove both untracked state files after verification. `--dry-run` must prevent all GitHub Issue and label mutations while still reporting the sanitized operations that would have occurred.

- [ ] **Step 6: Commit**

```bash
git add data/official-sources/monitoring-baselines.yaml data/official-sources/README.md .github/workflows/source-monitor.yml backend/tests/unit/knowledge/test_repository.py
git commit -m "ci: monitor reviewed official sources daily"
```

---

### Task 6: Migration 0005 and knowledge-source/requirement models

**Files:**
- Modify: `backend/app/database/enums.py`
- Modify: `backend/app/database/models.py`
- Create: `backend/app/domains/knowledge/__init__.py`
- Create: `backend/app/domains/knowledge/models.py`
- Create: `backend/migrations/versions/0005_knowledge_sources_and_requirements.py`
- Create: `backend/tests/integration/test_knowledge_schema.py`

**Interfaces:**
- Produces SQLAlchemy models: `KnowledgeSyncRun`, `KnowledgeSource`, `SourceRevision`, `Requirement`, `RequirementVersion`, `RequirementSource`
- Produces enums: `KnowledgeSyncStatus`, `KnowledgeSourceStatus`, `RequirementSupportType`
- Consumes: existing `Base`, `Actor`, `ServiceType`, and revision `0004_events_audit_and_immutability`

- [ ] **Step 1: Write failing PostgreSQL schema tests**

Test valid insertion plus exact rejection of duplicate source codes/URLs, invalid enum text, duplicate successful sync for one Git SHA, non-positive requirement version numbers, duplicate requirement fingerprints, missing source provenance at transaction commit, update/delete of revisions/versions/links, and restrictive foreign-key deletion.

- [ ] **Step 2: Run focused tests and verify RED**

```bash
cd backend
uv run pytest tests/integration/test_knowledge_schema.py -v
```

Expected: FAIL during import because knowledge models and migration do not exist.

- [ ] **Step 3: Add typed mappings and revision 0005**

Use UUID primary keys, `timestamptz`, JSONB validation summaries/conditions, lowercase hex checks for hashes, named checks/uniques/indexes, and `ON DELETE RESTRICT`. Persist source title/authority/jurisdiction/language/topics and requirement-version stage/responsible actor/level because each affects meaning or provenance. Add a partial unique index equivalent to:

```sql
CREATE UNIQUE INDEX uq_knowledge_sync_run_success_git_sha
ON knowledge_sync_run (git_commit_sha)
WHERE status = 'SUCCEEDED';
```

Create deferred constraint triggers that require at least one `requirement_source` for each material requirement version at commit. Create append-only triggers for `source_revision`, `requirement_version`, and `requirement_source`.

- [ ] **Step 4: Render and inspect offline SQL**

```bash
ALEMBIC_CONFIG=alembic.ini uv run alembic upgrade head --sql > /tmp/phase-2b-2a-0005-up.sql
ALEMBIC_CONFIG=alembic.ini uv run alembic downgrade 0004_events_audit_and_immutability --sql > /tmp/phase-2b-2a-0005-down.sql
```

Verify named objects and reverse dependency order; remove the temporary SQL files.

- [ ] **Step 5: Apply migration and run focused tests**

```bash
ALEMBIC_CONFIG=alembic.ini uv run alembic upgrade head
uv run pytest tests/integration/test_knowledge_schema.py -v
uv run ruff check app tests/integration/test_knowledge_schema.py migrations
uv run ruff format --check app tests/integration/test_knowledge_schema.py migrations
uv run mypy app
```

Expected: all pass against the disposable PostgreSQL test database.

- [ ] **Step 6: Commit**

```bash
git add backend/app/database backend/app/domains/knowledge backend/migrations/versions/0005_knowledge_sources_and_requirements.py backend/tests/integration/test_knowledge_schema.py
git commit -m "feat: persist versioned official requirements"
```

---

### Task 7: Repository artifact loader, DSL validation, and fingerprints

**Files:**
- Create: `backend/app/knowledge/dsl.py`
- Create: `backend/app/knowledge/fingerprints.py`
- Extend: `backend/app/knowledge/repository.py`
- Create: `backend/tests/unit/knowledge/test_dsl.py`
- Create: `backend/tests/unit/knowledge/test_fingerprints.py`
- Extend: `backend/tests/unit/knowledge/test_repository.py`
- Create: `backend/tests/fixtures/knowledge/synthetic_repository/`

**Interfaces:**
- Produces: `KnowledgeBundle = load_knowledge_bundle(root: Path, git_sha: str) -> KnowledgeBundle`
- Produces: `validate_requirement_condition(value: object) -> str | dict[str, object]`
- Produces: `validate_rule_condition(value: object, *, max_depth: int = 8) -> dict[str, object]`
- Produces: `canonical_fingerprint(value: Mapping[str, object]) -> str`
- Produces: `requirement_fingerprint(requirement, provenance) -> str`
- Produces: `rule_fingerprint(rule, requirement_versions) -> str`
- Produces: `rule_set_fingerprint(release, rule_fingerprints) -> str`
- Consumes: current registry, requirement, rule, dataset, and policy-contract artifacts

- [ ] **Step 1: Write failing repository-bundle tests**

Use a complete synthetic repository fixture. Test clean successful loading plus duplicate codes, unknown source/requirement references, version mismatch, changed release content without semantic-version bump, malformed Git SHA, and a provided SHA different from repository `HEAD`.

- [ ] **Step 2: Write failing DSL allowlist tests**

For requirements, allow only the literal `always` or the current `field`/`operator`/`value` leaf form, including `eq`, `in`, and `in_dataset`. For rules, allow only `all`, `any`, and the current `fact`/`operator`/`value` leaf form with `eq`, `neq`, `in`, `not_in`, `gte`, `lte`, `present`, `absent`, and `dataset_contains`. Reject unknown operators/keys, mixed logical and leaf forms, excessive depth, non-JSON values, unknown dataset IDs, and unknown outcome/task codes.

- [ ] **Step 3: Write failing fingerprint tests**

Prove YAML mapping/list presentation noise and provenance order do not change fingerprints. Prove that requirement stage/actor/level, statement, condition, machine handling, locator, support type, release scope, outcome contract, default outcome, dataset snapshot, rule description, finding code, priority, outcome, task, supplemental source codes, or referenced requirement-version changes do.

- [ ] **Step 4: Run tests and verify RED**

```bash
cd backend
uv run pytest tests/unit/knowledge/test_repository.py tests/unit/knowledge/test_dsl.py tests/unit/knowledge/test_fingerprints.py -v
```

Expected: FAIL because the bundle, DSL, and fingerprint interfaces are incomplete.

- [ ] **Step 5: Implement strict loading and canonical SHA-256 fingerprints**

Canonicalize with sorted JSON keys, compact separators, UTF-8, normalized strings, and sorted provenance records before hashing. Use subprocess arguments, never a shell string, for `git rev-parse HEAD` and `git status --porcelain`. Reject a dirty tree before parsing formal artifacts.

- [ ] **Step 6: Run all non-network unit and knowledge-contract tests**

```bash
uv run pytest tests/unit/knowledge -v
uv run ruff check app/knowledge tests/unit/knowledge
uv run ruff format --check app/knowledge tests/unit/knowledge
uv run mypy app
cd ..
ruby scripts/validate_knowledge_base.rb
ruby tests/rules/student-pass-v1.policy_contract_test.rb
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/knowledge backend/tests/unit/knowledge backend/tests/fixtures/knowledge
git commit -m "feat: validate repository knowledge bundles"
```

---

### Task 8: Migration 0006 and rule governance models

**Files:**
- Modify: `backend/app/database/enums.py`
- Modify: `backend/app/database/models.py`
- Modify: `backend/app/domains/knowledge/models.py`
- Create: `backend/migrations/versions/0006_rule_versions_and_activation.py`
- Create: `backend/tests/integration/test_rule_governance_schema.py`

**Interfaces:**
- Produces models: `RuleSet`, `RuleSetVersion`, `RuleDefinition`, `RuleVersion`, `RuleRequirement`, `ApprovalEvent`
- Produces enums: `RuleSetVersionStatus`, `ApprovalDecision`, `ApplicabilityBasis`
- Broadens existing `AuditEvent.case_id` only for constrained knowledge-governance entity types
- Consumes: Task 6 revision 0005 and models

- [ ] **Step 1: Write failing PostgreSQL governance tests**

Test valid DRAFT releases plus exact rejection of duplicate semantic versions, changed fingerprint for a reused semantic version, missing rules, missing rule provenance, non-administrator approvals, a second decision, approval after rejection, direct immutable content updates, invalid status transitions, two ACTIVE releases, and null-case audit rows for unapproved entity types.

- [ ] **Step 2: Run focused tests and verify RED**

```bash
cd backend
uv run pytest tests/integration/test_rule_governance_schema.py -v
```

Expected: FAIL because revision 0006 and rule-governance mappings do not exist.

- [ ] **Step 3: Implement models and migration**

Use text-backed Python enums and named checks. Persist each release's scope, outcome contract, default outcome, and small supporting dataset snapshots as validated JSONB. Persist each rule version's description, finding code, and validated supplemental source codes. Add deferred triggers requiring a rule-set version to contain at least one rule and every rule version to have requirement provenance. Protect rule versions, provenance, and approvals with append-only triggers. Protect rule-set version semantic content while allowing only guarded status/activated timestamp transitions.

Alter `audit_event.case_id` to nullable and add a check equivalent to:

```sql
CHECK (
  case_id IS NOT NULL
  OR entity_type IN ('KNOWLEDGE_SYNC_RUN', 'RULE_SET_VERSION', 'APPROVAL_EVENT')
)
```

Add the `(entity_type, entity_id, occurred_at)` index and preserve append-only audit triggers.

- [ ] **Step 4: Verify offline SQL, live migration, and focused tests**

```bash
ALEMBIC_CONFIG=alembic.ini uv run alembic upgrade head --sql > /tmp/phase-2b-2a-0006-up.sql
ALEMBIC_CONFIG=alembic.ini uv run alembic downgrade 0005_knowledge_sources_and_requirements --sql > /tmp/phase-2b-2a-0006-down.sql
ALEMBIC_CONFIG=alembic.ini uv run alembic upgrade head
uv run pytest tests/integration/test_rule_governance_schema.py -v
uv run ruff check app tests/integration/test_rule_governance_schema.py migrations
uv run ruff format --check app tests/integration/test_rule_governance_schema.py migrations
uv run mypy app
rm /tmp/phase-2b-2a-0006-up.sql /tmp/phase-2b-2a-0006-down.sql
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/database backend/app/domains/knowledge backend/migrations/versions/0006_rule_versions_and_activation.py backend/tests/integration/test_rule_governance_schema.py
git commit -m "feat: add immutable rule governance schema"
```

---

### Task 9: Atomic and idempotent knowledge synchronization

**Files:**
- Create: `backend/app/knowledge/sync.py`
- Extend: `backend/app/knowledge/cli.py`
- Create: `backend/tests/integration/test_knowledge_sync.py`

**Interfaces:**
- Produces: `KnowledgeSynchronizer.sync(root: Path, expected_git_sha: str) -> SyncResult`
- Produces CLI: `python -m app.knowledge.cli sync --root PATH --git-sha SHA`
- Consumes: Task 7 `KnowledgeBundle`/fingerprints and Tasks 6/8 models

- [ ] **Step 1: Write failing synchronization tests**

Test a complete synthetic import, same-commit idempotency, unchanged-version reuse, changed-version creation, failed validation with no formal rows, deferred provenance failure with no formal rows, retry after failure, stale STARTED recovery, and sanitized error summaries. Inject a failure after requirements and before rules to prove the formal transaction is atomic.

- [ ] **Step 2: Run focused tests and verify RED**

```bash
cd backend
uv run pytest tests/integration/test_knowledge_sync.py -v
```

Expected: FAIL because `KnowledgeSynchronizer` does not exist.

- [ ] **Step 3: Implement the explicit transaction protocol**

```text
transaction A: insert STARTED run; commit
transaction B: import/reuse all formal rows; set same run SUCCEEDED; commit together
on B failure: rollback B; transaction C marks the existing run FAILED
recovery: mark stale STARTED runs FAILED only after proving no formal rows reference them
```

Acquire an advisory lock derived from the Git SHA. Use stable business codes for identities and fingerprints for version reuse. Never merge dictionaries into existing immutable rows.

- [ ] **Step 4: Add the sync CLI boundary**

The CLI requires `--root` and `--git-sha`, prints only run ID/status/counts, returns 0 for a new or idempotent success, 2 for repository/validation failure, and 3 for database failure. It must not print database URLs or raw source content.

- [ ] **Step 5: Run focused, schema, and static checks**

```bash
uv run pytest tests/integration/test_knowledge_schema.py tests/integration/test_rule_governance_schema.py tests/integration/test_knowledge_sync.py -v
uv run ruff check app tests migrations
uv run ruff format --check app tests migrations
uv run mypy app
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/knowledge/sync.py backend/app/knowledge/cli.py backend/tests/integration/test_knowledge_sync.py
git commit -m "feat: synchronize reviewed knowledge atomically"
```

---

### Task 10: Review and administrator approval service

**Files:**
- Create: `backend/app/knowledge/governance.py`
- Extend: `backend/app/knowledge/cli.py`
- Create: `backend/tests/integration/test_rule_governance.py`

**Interfaces:**
- Produces: `submit_for_review(session: Session, version_id: UUID, actor_id: UUID, now: datetime) -> RuleSetVersion`
- Produces: `decide_release(session: Session, version_id: UUID, administrator_id: UUID, decision: ApprovalDecision, notes: str | None, now: datetime) -> ApprovalEvent`
- Produces CLI subcommands: `review` and `decide`
- Consumes: Task 8 governance schema

- [ ] **Step 1: Write failing governance-service tests**

Test DRAFT-to-REVIEW only after successful sync and complete provenance, approved/rejected decisions only in REVIEW, administrator-only enforcement at both service and direct-SQL boundaries, bounded notes, one final decision, and rejection requiring a new release.

- [ ] **Step 2: Run focused tests and verify RED**

```bash
cd backend
uv run pytest tests/integration/test_rule_governance.py -v
```

Expected: FAIL because governance services do not exist.

- [ ] **Step 3: Implement service and CLI**

Lock the rule-set-version row before transition. Require timezone-aware `now`. `decide_release` appends the approval event and a null-case `audit_event` in one transaction. The CLI accepts UUIDs, never creates actors, and returns stable exit codes without exposing connection details.

- [ ] **Step 4: Run governance regression checks**

```bash
uv run pytest tests/integration/test_rule_governance_schema.py tests/integration/test_rule_governance.py -v
uv run ruff check app tests/integration
uv run ruff format --check app tests/integration
uv run mypy app
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/knowledge/governance.py backend/app/knowledge/cli.py backend/tests/integration/test_rule_governance.py
git commit -m "feat: govern rule releases with human approval"
```

---

### Task 11: Locked activation and application-start catch-up

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/main.py`
- Create: `backend/app/knowledge/activation.py`
- Create: `backend/app/knowledge/scheduler.py`
- Extend: `backend/app/knowledge/cli.py`
- Create: `backend/tests/unit/knowledge/test_activation.py`
- Create: `backend/tests/integration/test_activation_schema.py`
- Create: `backend/tests/integration/test_activation.py`

**Interfaces:**
- Produces: `ActivationCoordinator.activate_due(session: Session, now: datetime) -> ActivationSummary`
- Produces: `display_release_status(version: RuleSetVersion, decision: ApprovalEvent | None, now: datetime) -> str`
- Produces: `run_activation_poll(stop: asyncio.Event, interval_seconds: int, coordinator_factory: Callable[[], ActivationCoordinator]) -> None`
- Produces CLI: `python -m app.knowledge.cli activate-due --at ISO8601`
- Adds setting: `knowledge_activation_poll_seconds: int = 60`, where `0` disables periodic polling but not an explicit invocation
- Consumes: Tasks 8 and 10

- [ ] **Step 1: Write failing clock-controlled activation tests**

Test no early activation, due activation, old ACTIVE retirement, approved future release display derivation, missing approval, rejected release, failed sync, overlap, invalid supersession, two concurrent attempts, database-error rollback, and catch-up after the effective time.

- [ ] **Step 2: Run focused tests and verify RED**

```bash
cd backend
uv run pytest tests/unit/knowledge/test_activation.py tests/integration/test_activation.py tests/integration/test_activation_schema.py -v
```

Expected: FAIL because activation interfaces do not exist.

- [ ] **Step 3: Implement locked activation**

For each due rule set, acquire a transaction-scoped PostgreSQL advisory lock, requery under the lock, verify exactly one approval and a successful sync, confirm `effective_at <= now`, and select the existing ACTIVE predecessor. Retire and activate in one transaction, set `activated_at = now`, and append one null-case `audit_event` containing only version IDs/statuses. On any exception, roll back the whole rule-set switch and continue only when the error is classified as isolated and safe.

- [ ] **Step 4: Implement startup and periodic scheduling**

Use the FastAPI lifespan to run one synchronous activation catch-up through `asyncio.to_thread`, then start one cancellable poll loop when the interval is positive. Tests set the interval to zero unless explicitly testing the scheduler. Shutdown sets the event and awaits the task; no orphan task may remain.

- [ ] **Step 5: Implement manual CLI and verify all activation tests**

Require an offset-aware ISO-8601 `--at`; default to the current UTC clock only when omitted. Print activated/skipped/failed counts without database details.

```bash
uv run pytest tests/unit/knowledge/test_activation.py tests/integration/test_activation.py tests/integration/test_activation_schema.py -v
uv run ruff check app tests
uv run ruff format --check app tests
uv run mypy app
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/config.py backend/app/main.py backend/app/knowledge backend/tests/unit/knowledge/test_activation.py backend/tests/integration/test_activation.py backend/tests/integration/test_activation_schema.py
git commit -m "feat: activate approved rule releases safely"
```

---

### Task 12: Migration round trip, CI, documentation, and full acceptance

**Files:**
- Modify: `backend/tests/migration/test_migration_round_trip.py`
- Modify: `.github/workflows/backend-ci.yml`
- Modify: `backend/README.md`
- Modify: `README.md`
- Modify: `CONTRIBUTING.md`
- Modify: `docs/research/PHASE_1_OFFICIAL_KNOWLEDGE_BASE.md`

**Interfaces:**
- Produces: exact six-revision migration round-trip evidence
- Produces: CI coverage for monitor fixtures, synchronization, governance, activation, migrations, and existing rule contracts
- Produces: operator instructions for bootstrap, monitor dry-run, sync, review, decision, activation, and portfolio-first limitations
- Consumes: all prior tasks

- [ ] **Step 1: Extend the migration test and verify it fails before final parity updates**

Require the exact graph:

```text
0001_identity_and_reference
0002_case_and_student_pass
0003_submissions_and_documents
0004_events_audit_and_immutability
0005_knowledge_sources_and_requirements
0006_rule_versions_and_activation
```

Exercise `base → head → 0004 → head → base → head`, compare all 26 mapped/migrated tables and columns, and verify every new function, trigger, partial index, and audit constraint at head.

- [ ] **Step 2: Run migration RED/GREEN verification**

```bash
cd backend
uv run pytest tests/migration/test_migration_round_trip.py -v
```

Expected after parity implementation: PASS and database restored to head from `finally`.

- [ ] **Step 3: Extend Backend CI without broadening permissions**

Keep `contents: read`, PostgreSQL 18.x, migrations before tests, Ruff, formatting, strict mypy, Ruby knowledge validation, and policy-contract validation. The backend test command discovers all new tests. Do not grant Issue write permission to Backend CI; only `source-monitor.yml` receives it.

- [ ] **Step 4: Document the exact operating sequence**

Document locked dependency install, database readiness, six migrations, monitor dry-run, explicit-SHA sync, administrator review/decision, manual activation, startup catch-up, safe shutdown, error exit codes, and synthetic-only test data. State clearly that local Docker is not always-on and that public use requires a persistent cloud database, managed secrets, and an independent worker.

- [ ] **Step 5: Run the full local acceptance suite**

```bash
cd backend
uv run ruff check app tests migrations
uv run ruff format --check app tests migrations
uv run mypy app
uv run pytest tests -v
cd ..
ruby scripts/validate_knowledge_base.rb
ruby tests/rules/student-pass-v1.policy_contract_test.rb
git diff --check
git status --short
```

Expected: every command passes; only intended Phase 2B.2A files are modified; the known upstream TestClient deprecation warning may remain documented but no new warning is accepted without review.

- [ ] **Step 6: Perform publication safety review**

Verify the Git manifest excludes `.env`, monitor state, candidate baselines, `.superpowers`, `.uv-cache`, virtual environments, Python/test/type/lint caches, logs, keys, full downloaded pages, private applicant paths, and real documents. Verify `.env.example` contains only disposable localhost values.

- [ ] **Step 7: Commit**

```bash
git add .github/workflows/backend-ci.yml backend/tests/migration/test_migration_round_trip.py backend/README.md README.md CONTRIBUTING.md docs/research/PHASE_1_OFFICIAL_KNOWLEDGE_BASE.md
git commit -m "docs: complete Phase 2B.2A operating guide"
```

- [ ] **Step 8: Push, open a PR, and require remote checks before merge**

Push the implementation branch, open a PR titled `feat: implement Phase 2B.2A knowledge synchronization`, confirm the public changed-file manifest, and require both Backend CI and source-monitor workflow validation to pass. Do not merge on local evidence alone and do not delete the branch before the merged `main` workflow succeeds.

## Acceptance-criteria coverage

| Spec criterion | Implementation and proof |
|---|---|
| Twelve tables plus constrained platform audit entries | Tasks 6 and 8 create six tables each; Tasks 8 and 12 verify the broadened `audit_event` constraint and index. |
| PostgreSQL-enforced immutable versions and provenance | Tasks 6 and 8 add append-only and deferred provenance triggers; Task 12 verifies every trigger after a migration round trip. |
| Exact provenance for every requirement and rule | Tasks 6–9 validate and persist requirement-to-source and rule-to-requirement links. |
| Clean explicit Git SHA, atomicity, and idempotency | Tasks 7 and 9 reject dirty or mismatched repositories and test repeated synchronization. |
| Failed synchronization without partial formal data | Task 9 tests the three-transaction protocol and injected mid-import failure. |
| Administrator-only approval or rejection | Tasks 8 and 10 enforce the actor type in both PostgreSQL and the service boundary. |
| Future approval remains non-active | Tasks 10 and 11 test derived `SCHEDULED` display and prohibit early activation. |
| Locked, atomic, auditable, failure-safe activation | Task 11 tests locking, concurrency, rollback, retirement, activation, and audit emission. |
| Daily and manual monitoring cannot mutate formal rules | Tasks 3–5 isolate monitoring from synchronization and provide both triggers. |
| One sanitized Issue for a changed or blocked source | Task 4 tests hidden-marker deduplication, label setup, update behavior, and redaction. |
| Third consecutive scheduled failure becomes `BLOCKED` | Task 3 covers every scheduled/manual failure-state transition. |
| No full pages, secrets, or real personal/document data | Tasks 1–5 bound monitor records; Task 12 performs the publication-safety review. |
| Existing phases remain green | Tasks 7, 9–12 run the existing Ruby contracts and the complete backend regression suite. |
| No Phase 2B.2B case evaluation or business APIs | Global Constraints prohibit them; Task 12 verifies only intended Phase 2B.2A files changed. |
| Portfolio-first limitation and public-production path documented | Task 12 records local limitations and the future persistent database, managed-secret, independent-worker deployment. |
