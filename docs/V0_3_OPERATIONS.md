# V0.3 Developer Planner & Tester Runner

This is a **safe deterministic prototype**, not an autonomous LLM software engineer.
It does not generate actual source code, clone repositories, use GitHub write
tokens, open pull requests itself or run untrusted tasks in a hardened sandbox.

## Developer planning

```bash
python -m agency.v03_cli propose --task examples/v03_task.json --out out/proposal.json
```

The planner enforces a `feat/` branch, a full base commit SHA,
`REVIEW_ONLY`/`PAPER` mode, and allowlisted paths. It **only writes
a local proposal JSON**; a human must decide which source changes to make.
No task instruction is interpreted as a shell command.

## Tester runner (trusted checked-out code ONLY)

```bash
python -m agency.v03_cli test --repo . --out-dir /tmp/baoxtra-v03-evidence --report out/tester-report.json
```

Runs a fixed unittest command (no shell), with timeout and exit-code/log SHA-256
receipt. It must run on a disposable CI runner for third-party code; ordinary
subprocess isolation is **NOT** an adversarial security sandbox. Local status
`LOCAL_TEST_PASS_UNTRUSTED` is **not** Trusted CI or Verified E2E.

## Handoff policy

- Developer produces review-only proposal.
- Human reviews and approves changes; separate CI runs against exact SHA.
- Tester logs are local-untrusted until independently authenticated.
- Independent Verifier V0.2 validates only GitHub metadata.
- No live trading, auto merge, main branch writes, or deployment.
- PR must pass branch rules and GitHub Actions before owner merge.

## V0.4 needed

- LLM developer with constrained workspace and no broad credentials.
- Independent disposable execution sandbox + test artifacts authenticated to CI.
- GitHub App fine-grained Draft PR adapter and reviewer identity separation.
- Durable append-only audit, E2E scenarios and Work 200 bridge.
