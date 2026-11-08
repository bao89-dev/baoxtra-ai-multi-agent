# V0.5 Workspace intake — scope and frontend contract

This branch is based on `feat/v0.4-control-api` (Draft PR #4), NOT main. Merge V0.4 first or retarget carefully. No AI model, transcription, diagram generation, execution or media scanner is connected.

## API
Authenticated via server-side `AGENCY_API_TOKEN`, never expose token to browser:
- `POST /api/v1/conversations` JSON `{"title":"My project"}`
- `GET /api/v1/conversations`
- `POST /api/v1/conversations/{id}/messages` JSON `{"text":"Review screenshot","attachment_ids":["<uploaded-id>"]}`
- `GET /api/v1/conversations/{id}/messages`
- `POST /api/v1/conversations/{id}/attachments` multipart form `file`
- `GET /api/v1/conversations/{id}/attachments` metadata only, never raw bytes
- `GET /api/v1/conversations/{id}/events?after=0` SSE with `Last-Event-ID` replay; use `?once=true` only for testing.

## Media
PNG, JPEG max 8 MiB; MP4 max 25 MiB. Header signature and MIME declaration checked (not full parser/AV). Opaque filename in private `AGENCY_UPLOAD_PATH`; `SHA-256` persisted. All files remain `QUARANTINED_NOT_SCANNED`, `analysis: NOT_RUN`. Never serve, preview, transcribe, inspect with LLM or execute quarantined files. For production add real malware scanning, storage isolation, stronger format parsing, quota and rate limiting, retention/deletion, user-scoped auth, encryption and async media workers.

## Chat
Messages are persisted as owner messages only. Posting text does not call an LLM. Stream emits **event notifications**, not AI tokens. SSE connection closes after ~20 seconds; frontend reconnects with cursor, and uses authenticated Next.js BFF to keep bearer token server-side. No deployment URL yet.

## Safety and acceptance
No `VERIFIED` by user submission, no direct trading orders, no autonomous branch/PR actions. New tests cover auth, history, event replay, signature mismatch, attachment ownership, and quarantined video. CI status needs real logs before claimed VERIFIED. Multi-user permission and authenticated owner approval gate are NOT_IMPLEMENTED.

## Next
1. Add frontend BFF + Chat/Files UI.
2. Add isolated AV scan, job queue, object storage.
3. Add consent-based vision/video workers, citations to frames and timecodes.
4. Add versioned diagram + plan, owner approval and audit.
