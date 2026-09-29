# Student Pass V1 demo guide

## Prerequisites

- Docker Desktop running
- Node.js 24 with npm
- `uv`
- GNU Make

No cloud account, paid API key, or real applicant data is required.

## Start and stop

From the repository root:

```bash
make demo
```

Open `http://127.0.0.1:4173`. The command installs locked dependencies when needed, starts PostgreSQL, applies migrations, imports the reviewed repository knowledge bundle, records a synthetic review and administrator approval, activates the due release, and starts both applications. Database credentials are not printed.

Stop only this demo's processes and PostgreSQL container while preserving its local volume:

```bash
make demo-stop
```

## Reviewer walkthrough

1. Select **Explore as Applicant**.
2. Open **Requirements** and inspect the current source-derived requirement preview. A draft previews current policy but is not yet bound to it.
3. Open **Readiness** to see deterministic evaluation history.
4. Open **Handover**, select **Submit to Immigration**, and confirm. The server timestamp now fixes the applicable rule version; this is applicant handover, not official acceptance or approval.
5. Select **Switch workspace**, then **Explore as Officer**.
6. Open the submitted synthetic case and inspect its rule version, findings, and safe event timeline.
7. Select **Start processing**. The case becomes `IN_PROCESS`; there is deliberately no AI approval or rejection control.

Use **Reset demo** on the landing page to withdraw the current synthetic case and prepare a new draft. Existing append-only audit evidence is preserved.

## Verification

```bash
make test
```

This applies migrations to an isolated test database, runs backend tests and static checks, validates the knowledge bundle, runs frontend lint/type/unit/build gates, and executes the Chromium cross-role smoke path.

## Synthetic-data and trust boundary

This repository contains synthetic identities and metadata only. It must never receive real passport files, identity numbers, credentials, medical information, or applicant records. `X-Actor-Id` is a demo mechanism, not authentication. The project is independent, is not connected to Malaysian Immigration or EMGS, does not provide legal advice, and does not make official decisions. Always verify requirements with the cited authorities.

## Why the portfolio demo is local

The current demo is intentionally local instead of always-on: public hosting would require paid infrastructure and proper secret/key management before it could be operated responsibly. A real public deployment needs real authentication, reviewed authorization policies, managed PostgreSQL, encrypted object storage, secrets management, monitoring and alerting, retention/deletion controls, backups and restore drills, abuse protection, and independently supervised scheduled official-source monitoring.

## Troubleshooting

- If Docker is unavailable, start Docker Desktop and rerun `make demo`.
- If port 5432, 8000, or 4173 is occupied, stop the conflicting local service. Test PostgreSQL defaults to port 55433 and can be overridden with `TEST_POSTGRES_PORT`.
- Inspect `.demo-runtime/backend.log` or `.demo-runtime/frontend.log` if a process fails to start. Logs and credentials are not committed.
- Install Chromium once with `npm --prefix apps/immigration-flow-web exec playwright install chromium` if Playwright reports a missing executable.
