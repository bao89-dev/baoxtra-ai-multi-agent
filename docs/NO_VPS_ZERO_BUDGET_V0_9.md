# BaoXTra AI Agency — No-VPS development profile (V0.9)

## Goal
Provide a realistic **$0 infrastructure baseline** for code review and CI without pretending the complete Agency is free or always-on.

### Zero-spend defaults
```env
AGENCY_PAID_OPERATIONS_ENABLED=false
AGENCY_DAILY_BUDGET_USD=0
AGENCY_TASK_BUDGET_USD=0
```

`/api/v1/cost-policy` reports effective policy. `POST /api/v1/cost-reservations` fails closed until the operator explicitly enables paid operations **and** sets positive budgets. This endpoint only records an allowance; it makes no external model call and does not charge or invoke an LLM. **Future workers MUST enforce this before any billable action**, and independently verify actual provider billing. Reservations persist without release in V0.9 intentionally: fail-safe but requires a production reconciliation/lifecycle implementation before use.

## Free workflow for now
- Store code in existing GitHub repository.
- Run unit/build/security contract tests using GitHub Actions within account allowance. Avoid paid Actions features and review usage/budgets periodically.
- Run FastAPI and Next.js locally when using a desktop; there is no always-on backend while laptop is off.
- Keep ChatGPT/Notion as project communication and documentation layer. ChatGPT subscription is separate from developer API fees.
- No paid LLM credentials and no external hosting required for CI-only source development.

## If mobile access from iPhone is required without a VPS
A managed free-tier web service may host test environments, but limitations make it **unsuitable for this exact API without changes**:
- Existing SQLite, quarantined images/videos on local disk and common shared password are NOT safe/durable in free ephemeral hosting.
- Render Free spins down after idle and loses local filesystem state on restart/deploy; free PostgreSQL has limited lifetime. Do NOT deploy private media this way.
- A stateless authenticated frontend can be considered after migrating database/storage to managed persistent services and completing IAM, rate limiting, media scanning and browser E2E.
- Serverless frontends do not automatically replace long-running Agent sandbox workers or image/video pipelines. No plan guarantees free unlimited usage.

## When the owner must authorize costs
1. Any paid AI API, image/video inference, hosted database/storage, extra CI minutes, sandbox compute or managed application hosting.
2. Configure usage alerts and capped provider budgets **in the provider account itself**, not solely via agency database.
3. Approve additional identity infrastructure, credit card or OAuth before external deploy.
4. Never set `AGENCY_PAID_OPERATIONS_ENABLED=true` until workers, billing reconciliation, independent approval and operational evidence are implemented.

## Work queue
P0: private authenticated staging and durable storage design; media quarantine scanner, session hardening, real browser checks.
P1: isolated worker + CI provenance/independent verifier; versioned approval and handoff integration.
P2: opt-in LiteLLM model router with request-by-request budgets and explicit provider billing alerts.
P3: Telegram notifications as secondary interface (web dashboard remains primary).
Maintain REVIEW_ONLY/PAPER. Do not auto merge, deploy, or submit live trading orders.

## Pricing reference (verified November 2026)
GitHub Free includes quota for private repository CI; public standard Actions are free (subject to GitHub policies). Render Free has idle spin-down and ephemeral filesystem. Gemini developer API supports a limited free tier with per-model quota and data-handling differences. Always recheck official pricing before enabling paid use.
