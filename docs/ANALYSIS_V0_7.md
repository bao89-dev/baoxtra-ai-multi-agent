# V0.7 Analysis Job Gate — implementation report

**Purpose:** build the first traceable intake for image/video review requests from BaoXTra Agency Control Center. This version does NOT process, view, decode, scan, transcribe or analyze media, and makes no AI provider calls. The strongest allowed outcome is BLOCKED_SECURITY.

## Branch / dependency
- Repository: `bao89-dev/baoxtra-ai-multi-agent`
- Feature branch: `feat/v0.7-analysis-jobs-gate`
- Base: `feat/v0.4-control-api` (the current integration branch containing merged V0.5 + V0.6 according to reviewed source paths)
- Keep Draft PR and human approval before merge or release.
- Do not infer main contains these changes.

## New backend contract
- `POST /api/v1/conversations/{conversation_id}/analysis-jobs` authenticated JSON:
```json
{
  "attachment_id": "<attachment UUID>",
  "job_type": "image_review",
  "instructions": "Review the UI layout and suggest application components."
}
```
- `GET /api/v1/conversations/{conversation_id}/analysis-jobs`
- `GET /api/v1/analysis-jobs/{job_id}`

The POST checks that the conversation and attachment exist, validates relationship between them, enforces image/video MIME vs job type, and persists an immutable blocked job record. It emits `analysis.blocked` SSE event for the existing chat. No endpoint to mark a job `COMPLETED` or to run workers.

### Response example (not evidence of an actual AI run)
```json
{
  "id": "<uuid>",
  "status": "BLOCKED_SECURITY",
  "blocker": "QUARANTINED_NOT_SCANNED: isolated media scanner and approved AI worker missing",
  "result_summary": null,
  "model_executed": false
}
```

## UI / Next.js BFF
- The Files tab includes a form to select previously uploaded media, add instructions, submit an analysis request, and view blocked history.
- BFF allowlist supports only GET/POST analysis-jobs collection and GET job detail; prohibits PATCH, DELETE, worker execution, trading order and approval.
- All requests still require the signed owner development session and server-side bearer token. This is NOT production multi-user identity/access control.

## Release gates
1. Independent malware scan and complete file parser with trustworthy clean/quarantine state transitions, per-user authorization, signed evidence.
2. Restricted isolated analysis worker, rate limits/quotas, per-file consent, prompt-injection defense on untrusted media, no outbound secrets.
3. Async job worker lifecycle QUEUED/RUNNING/COMPLETED/FAILED with worker-side authentication, timeout, retry, provenance, structured output and timestamp/frame citations.
4. Frontend browser E2E, deployment TLS, persistent DB operations and owner approval gate.
5. Never fabricate model analysis, CI PASS, Work 200 pytest results, real MT5 results or production readiness.

## Test scope
Python tests: authorization, conversation/attachment ownership, MIME job mismatch, blocked job persistence/event, no public execution/update route. Frontend contract test: BFF route allows only review submission/read. Source/build tests require GitHub Actions log, commit and artifact evidence. REVIEW_ONLY/PAPER only.
