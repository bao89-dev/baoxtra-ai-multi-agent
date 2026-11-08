# Media Security Gate V1.0 — scanner adapter only

This is a **precondition** to AI Vision, not an AI Vision worker. Every uploaded media item remains quarantined until an operator runs a trusted AV scan in a dedicated, restricted scanner environment. The scanner is NOT called from the public HTTP API. The scanner does NOT make paid AI calls.

## Commands (only in a local or isolated scanner machine)

Install `clamscan` and its current official signature database using the platform's package/signature manager. Keep it updated and secure the scanner runtime.

```bash
export AGENCY_DB_PATH=./out/control-api.sqlite3
export AGENCY_UPLOAD_PATH=./out/quarantine
python -m agency.media_scan --attachment-id <uploaded-uuid>
```

For each file, the process compares UUID, MIME-derived filename, expected length and SHA-256 against database metadata before scanning, calls a fixed command with `shell=False`, enforces a timeout, and records a non-reversible result and event. No scan output or raw media is served to the user.

Statuses:
- `QUARANTINED_NOT_SCANNED` — upload received, unsafe for all further use.
- `AV_CLEAN_FORMAT_UNVERIFIED` — scanner returned clean, but file structure, decompression bombs, malformed media, privacy and AI prompt injection are not validated. **Still no AI processing permitted.**
- `MALWARE_DETECTED` — quarantine, never provide to inference.
- `SCAN_FAILED_CLOSED` — missing AV binary/signatures, timeout or scanner execution error; no AI.
- `INTEGRITY_MISMATCH` — file missing/symlink/changed/invalid path; no AI.

## Critical limitations
- There is no scanner/container isolation provided or deployed in this PR, and no full media parser. Operator must not run untrusted media scanner in a privileged host.
- A malicious media file can attack AV itself; use an isolated disposable low-privilege worker with no secrets/network and least filesystem access before production.
- A ClamAV "clean" result is only one check; a content-type-aware validator and media decoder with resource limits must also run before marking media ready.
- Local SQLite is a development-only deployment; scanner must share a trusted database/storage and be replaced with durable transaction/locking in a distributed hosted deployment.
- No HTTP endpoint changes beyond attachment metadata's existing status field.
- Do not claim media analysis, Vision output, sandbox E2E, browser QA or production safety on the basis of the contract tests.

## Next gates
1. Containerized non-root scanner execution, hardened container settings, signature age/version validation, no secrets/mounts.
2. Full PNG/JPEG/MP4 media parsers + resource/time/size limits, reject malformed media, strip sensitive metadata if appropriate.
3. Data retention, deletion, user-scoped object authorization, media worker queue and isolated AI API key access.
4. Consent, cost cap, human plan approval, browser Safari end-to-end test and independent verifier.
5. Finally integrate AI Vision, track frame and timecode evidence; keep REVIEW_ONLY/PAPER.
