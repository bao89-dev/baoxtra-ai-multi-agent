# Control Center Frontend V0.6 — Review-only

This is a **Next.js web UI and Backend-for-Frontend** for the V0.5 workspace APIs, not a deployed website. The frontend V0.6 branch is based on V0.5 (Draft PR #6), which in turn depends on V0.4 (Draft PR #4). Merge/rebase in dependency order after review.

## Local setup

1. Run the Python backend described in `docs/CONTROL_API_V0_4.md` with V0.5 routes.
2. `cd frontend && npm install`
3. Create `frontend/.env.local` (never commit):
   ```
   AGENCY_API_URL=http://127.0.0.1:8000
   AGENCY_API_TOKEN=<server-side-backend-token-at-least-24-chars>
   CONTROL_CENTER_PASSWORD=<long-password-at-least-16-chars>
   CONTROL_SESSION_SECRET=<random-server-secret-at-least-32-chars>
   ```
4. `npm run dev`, open `http://localhost:3000`.
5. `npm test && npm run build`.

## Implemented

- iPhone-responsive project workspace with conversations, owner chat, attachment upload, attachment quarantine status, and SSE event reconnect.
- Server BFF route allowlist and secure session cookie, constant-time password comparison, same-origin write checks, session expiration. Backend bearer token remains server-side, never in browser JS.
- Backend must accept ONLY REVIEW_ONLY/PAPER. UI shows that messages are stored but AI has NOT responded.
- Diagram/plan/approval is **placeholder only**, not active. No LLM, no malware scanner, no media playback, no production URL.

## Hardening blockers prior to Internet deployment

- Replace single shared password with identity provider, real per-user authorization and audit.
- Enforce reverse proxy rate limits for login, upload, chat; server-side quotas and request size limits before buffering, hardened origin checks for proxy setups.
- Proper anti-malware scanner, full media parser, storage TTL, object-level permissions and HTTPS/TLS for every external hop.
- Idempotency keys for mutations, pagination/retention, user roles, approval version signatures.
- Add browser E2E (e.g. Playwright mobile), production deployment verification, real independent artifact verification.

## API wiring

Browser -> same-origin `/api/session` login -> httpOnly signed cookie -> `/api/control/*` allowlisted proxy -> Python FastAPI with backend bearer auth.

Frontend uses `/api/control/conversations` and related nested routes. SSE uses EventSource auto reconnect and `Last-Event-ID`. Media is uploaded to server quarantine and *never* exposed for direct download/preview until scanning is implemented.

Expected status: code available in Draft PR; frontend test/build CI results must be checked for same commit before saying verified.
