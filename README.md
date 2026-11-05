# BaoXTra AI Multi-Agent

Security-first **AI Software Agency starter V0.2**. This repository contains
a working Python orchestration/validation skeleton and GitHub CI metadata
verifier, **not yet autonomous coding agents**.

## Run locally

```bash
python -m unittest discover -s tests -v
python -m agency.cli plan --input examples/charter.json --output out/plan.json
python -m agency.cli verify --input examples/task.json --output out/verification.json
```

## Verify GitHub CI metadata

```bash
python -m agency.cli verify-ci --repo bao89-dev/baoxtra-ai-multi-agent \
  --commit <FULL_SHA> --run-id <RUN_ID> --output out/ci-verification.json
```

For private repositories, use an Actions: Read token through the
`GITHUB_TOKEN` environment variable; never commit credentials.

### Implemented

- Project Charter gate, cycle-safe DAG planner, local evidence SHA-256 manifest.
- Fail-closed review stage and policy forbidding LIVE / auto merge.
- GitHub Actions unit tests plus attached log artifact.
- Read-only GitHub API metadata checks for workflow/job/artifact identities,
  exact commit SHA, completion and success, artifact presence.
- Negative-case unit tests and a CLI command for metadata verification.

### Still blocked / NOT_IMPLEMENTED

- AI Council and Developer/Tester with real LLM and coding execution.
- Artifact **content** authentication, workflow integrity attestation and
  independent cross-environment E2E verification.
- Persistent Evidence Store, independent verifier service, release/handoff
  automation, Work 200 live integration and MT5 tests.

**Do not interpret CI_METADATA_VERIFIED as a complete software acceptance.**
No live brokerage orders, auto-merge or deployment are enabled. Human review
remains mandatory. See [docs/VERIFICATION_V0_2.md](docs/VERIFICATION_V0_2.md).
