# V0.2: GitHub CI metadata verification

Invoke the read-only verifier with **an exact 40-character commit SHA** and a
specific GitHub Actions run ID:

```bash
python -m agency.cli verify-ci --repo bao89-dev/baoxtra-ai-multi-agent \
  --commit <40-character-sha> --run-id <positive-id> --output out/ci-verification.json
```

For private repositories, provide a fine-grained, **read-only** `GITHUB_TOKEN`
with Actions: Read. Never commit tokens or paste them in issues/logs.

Verification checks an API response for:
- Repo identity, full commit SHA, run status/conclusion, expected workflow path.
- Unit-test job on the same SHA and successful Unit tests / Upload CI log steps.
- A non-expired, nonempty `unit-test-log` artifact tied to the same run and SHA.
- Exact returned item counts: more than one page or ambiguous results fail closed.

A `CI_METADATA_VERIFIED` status means **only GitHub's run/job/artifact
metadata has been checked**. It does **not** authenticate the downloaded log
bytes, attest workflow integrity, satisfy independent acceptance evidence, or
authorize a merge/release. The result always includes
`HUMAN_APPROVAL_REQUIRED`, `auto_merge: false`, `live_execution: false`.

No network access is needed for offline negative tests:
`python -m unittest discover -s tests -v`.

Security limitation: The V0.1 local `validate_evidence` is not a
cryptographic attestation; self-reported fields must never be used as a
release authorization. Actual evidence provenance is checked only through
this read-only GitHub API metadata path. An independent verifier and
content-level artifact authentication remain pending.
