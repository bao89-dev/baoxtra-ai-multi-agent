# BaoXTra AI Agency V0.8 — versioned architecture proposals and human approval

## Purpose and limitations
This version delivers a persistent **proposal/decision registry**, not a diagram-generating AI, code agent, deployment engine, trading bot, or production-ready identity service. It provides the foundation for a user to describe app components, save Mermaid source and a DAG of tasks, revise the design, and explicitly approve/reject the **exact saved version**.

## Backend API (requires AGENCY_API_TOKEN)
- `POST /api/v1/proposals`: create version 1 for an existing conversation; fields `conversation_id,title,summary,diagram,tasks`
- `GET /api/v1/conversations/{cid}/proposals`: list current versions
- `GET /api/v1/proposals/{id}`: current draft, SHA-256 and decision
- `POST /api/v1/proposals/{id}/revisions`: exact `expected_version` plus full content; creates immutable V+1.
- `POST /api/v1/proposals/{id}/decision`: exact `expected_version,expected_sha256,action,reason`; requires separate `X-Owner-Approval-Key` matched to `AGENCY_APPROVAL_TOKEN`.

## Safety controls
- Task DAG rejects duplicate/unknown dependency and cycles; proposal JSON canonicalization and SHA-256 bind decisions to bytes of content.
- Versions are append-only. No action on an older version can authorize the newest version. A revision supersedes a prior approval; only the latest version's approval is presented as current.
- Only one decision for a given version (unique database constraint); stale version, hash mismatch and duplicate decisions fail closed.
- Owner approval credential must be at least 32 chars and distinct from backend API token. Never commit it, copy into Notion or expose it through frontend JavaScript.
- Every proposal and decision creates an SSE conversation event. No auto code, CI, GitHub write, trade order, merge or deployment is triggered.
- Frontend is **development-only single shared password**: not a production security boundary, not individual owner authentication or role-based access.

## Frontend
The Plan tab includes a versioned editor for title, scope, Mermaid source (stored as text), tasks (JSON), and explicit decisions. Editing a saved proposal disables action buttons until a revision is stored. To use decisions in local development set `AGENCY_APPROVAL_TOKEN` separately in **both the FastAPI backend environment and the server-side frontend .env.local**.

## Local QA
Run Python `python -m unittest discover -s tests -v`. For frontend: `cd frontend && npm install && npm test && npm run build`. CI metadata/logs must be read for final SHA and artifact before declaring tests verified.

## Missing work to reach user's ultimate requirements
1. Harden identity with per-user roles, MFA/SSO, session revocation, brute-force and rate limits, independent approval identity.
2. Media scan and full format validation, secure object storage, quotas and retention before any AI inference.
3. Isolated AI Vision/video worker with opt-in inference budget, correct provenance/frame timestamps, task execution limits.
4. Architecture AI council, collaborative editing and safe Mermaid rendering; no instructions from uploaded documents executed.
5. Scoped Developer/Tester/Verifier handoff, CI artifact byte verification, sandbox/browser E2E, staging HTTPS and mobile Safari QA.
6. GitHub branch protection remains mandatory, especially before any future automated PR creation. Human release approval is distinct from accepting a proposal.

## Current integration
V0.8 branched from `feat/v0.4-control-api`, where V0.5/V0.6/V0.7 had been merged. Keep Draft PR and don't merge main or deploy to production without review. Status `NOT_RUN` for all real-world execution, external LLM and browser checks.
