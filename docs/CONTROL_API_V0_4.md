# Control Center API V0.4 — frontend integration contract

Status: **feature branch / Draft PR; NOT_DEPLOYED**. This is a review-first task registry, not an autonomous coding agent, independent CI verifier, or brokerage execution service.

## Setup

Install: `python -m pip install -r requirements-control-api.txt`

Set environment variables (secrets must remain server-side):
- `AGENCY_API_TOKEN`: random bearer token, minimum 24 characters.
- `AGENCY_DB_PATH`: optional SQLite path, defaults to `./out/control-api.sqlite3`.
- `AGENCY_CORS_ORIGINS`: comma-separated explicit origins (optional; do not use wildcard).

Start locally: `uvicorn agency.control_api:app --host 127.0.0.1 --port 8000`

Tests: `python -m unittest discover -s tests -v`

## HTTP endpoints

All `/api/v1/*` endpoints require `Authorization: Bearer <token>`:

| Route | Function |
| --- | --- |
| `GET /health` | Liveness only; not CI/trading health |
| `GET /api/v1/summary` | Counts by status |
| `GET /api/v1/tasks` | Paginated list; filter by module/priority/status |
| `POST /api/v1/tasks` | Create NOT_RUN task |
| `GET /api/v1/tasks/{id}` | Task, evidence, audit history |
| `PATCH /api/v1/tasks/{id}` | Change metadata or NOT_RUN/BLOCKED/FAIL |
| `POST /api/v1/tasks/{id}/evidence` | Submit UNVERIFIED evidence |

Create task body:
```json
{"title":"Review BX42 parser","module":"bx42-parser","priority":"High","request":"Run parser tests and store logs","mode":"REVIEW_ONLY"}
```

Evidence body (illustrative, not verified):
```json
{"command":"python -m unittest discover -s tests -v","exit_code":0,"environment":"GITHUB_CI","commit_sha":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","artifact_sha256":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"}
```

Evidence remains **UNVERIFIED_SUBMISSION** regardless of claimed exit code. There is deliberately no endpoint to mark VERIFIED; independent run/artifact provenance and human approval are future work. Never treat source strings or Notion notes as CI proof. No LIVE mode, auto-merge, shell command runner or trading orders.

## Frontend handoff

Build a Next.js server-side BFF/route handler to hold `AGENCY_API_TOKEN`; do not expose the bearer token in the browser or `NEXT_PUBLIC_*` variables. Browser uses same-origin `/api/control/*`, while BFF proxies an explicit allowlist of backend calls. Display evidence verification separately from task status. Show health/stale/disconnected based on observed API health and last successful request; never infer CI or MT5 health from `/health`. Stop button must be labelled **UI only — not a real kill switch**.

Before Internet deployment: authenticated user sessions, TLS, rate limits, input and audit retention, reverse proxy, secure secret management, DB migrations, PostgreSQL for multi-replica setup, and CI provenance verification.

Tests expected locally: six contract/security scenarios. Remote CI run and PR are separate evidence and must be checked before stating VERIFIED.
