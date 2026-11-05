# BaoXTra AI Multi-Agent

Security-first **software development agency starter V0.1**. This is a working **offline contract validator**, not a completed autonomous coding agency.

Owner → Council charter gate → PM task DAG → Developer (planned) → GitHub CI → Evidence Store (planned) → Independent Verifier (local checks) → Handoff (planned).

## Run tests

```bash
python -m unittest discover -s tests -v
python -m agency.cli plan --input examples/charter.json --output out/plan.json
python -m agency.cli verify --input examples/task.json --output out/verification.json
```

## Implemented

- Charter validation; task graph cycle and unknown-dependency detection.
- Evidence manifest using SHA-256, source/exit checks and fail-closed independent review.
- GitHub Actions unit tests with uploaded test output artifact.
- 14 unit tests cover positive and rejection cases.

## NOT implemented

- LLM-backed Council/Developer/Tester agents; real code authoring, GitHub PR automation.
- Independently authenticated GitHub CI provenance; durable evidence store and audit log.
- Production release pipeline, live trading, automatic merges.

## Safety

Modes limited to REVIEW_ONLY and PAPER. Any LIVE, broker execution, withdrawal or auto-merge is disallowed. No approval is granted by local evidence alone. Human approval required for releases. CI green is not equivalent to verified E2E.

See docs/ARCHITECTURE.md and docs/ROADMAP.md. Always review CI checks and logs against the exact commit SHA before merging.
