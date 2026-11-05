# Rollout plan

- V0.1: Offline council/charter gate, deterministic DAG, local evidence manifest, fail-closed verifier, CLI, CI unit tests.
- V0.2: GitHub run provenance verification and artifact index with read-only integration.
- V0.3: Isolated Developer Agent and Tester Agent, draft PR-only permissions.
- V0.4: LLM-backed Tech Lead / Security / Product Owner council and auditable decisions.
- V1.0: Secure handoff, QA and DevOps gates, identity separation, operations and E2E evidence.

Acceptance evidence required: exact branch+commit SHA, workflow run and exit code, downloadable logs, negative fail-closed cases, manual gate, and separate GitHub CI / sandbox pytest / live E2E classifications. Do not claim verified for tests that have not run.
