# Work200 PR chain audit — 2026-11-08

Scope: read-only validation of the dependent PR chain #4 -> #9 -> #10 -> #11.
The script checks live GitHub PR base/head, open state and 40-character SHA. It does not
verify ancestry, CI provenance, same-SHA UI/backend approval E2E, or browser behavior.
No merge, deploy, order, or paid operations are performed.

Run: `python -m unittest discover -s tests -p 'test_pr_chain_audit.py' -v`
Then: `python -m scripts.audit_pr_chain` (requires GitHub API connectivity).

The actual local integrated-approval candidate described in Notion was NOT available
in this checkout; this PR does not claim to include or test that candidate.
