#!/usr/bin/env python3
"""Read-only GitHub dependency-chain audit; never merges or approves PRs."""
import json
import os
import sys
import urllib.error
import urllib.request

REPO = "bao89-dev/baoxtra-ai-multi-agent"
CHAIN = (4, 9, 10, 11)
EXPECTED = {
    4: ("main", "feat/v0.4-control-api"),
    9: ("feat/v0.4-control-api", "feat/v0.8-versioned-proposal-approval"),
    10: ("feat/v0.8-versioned-proposal-approval", "feat/v0.9-zero-vps-cost-guard"),
    11: ("feat/v0.9-zero-vps-cost-guard", "feat/v1.0-media-integrity-gate"),
}


def check(prs):
    failures = []
    evidence = []
    for number in CHAIN:
        p = prs[number]
        expected_base, expected_head = EXPECTED[number]
        base = p["base"]["ref"]
        head = p["head"]["ref"]
        sha = p["head"]["sha"]
        status = p["state"]
        merged = p.get("merged_at")
        if (base, head) != (expected_base, expected_head):
            failures.append(f"PR #{number}: wrong base/head {base} <- {head}")
        if status != "open" or merged:
            failures.append(f"PR #{number}: not an open unmerged PR")
        if len(sha) != 40 or any(c not in "0123456789abcdef" for c in sha):
            failures.append(f"PR #{number}: invalid head SHA")
        evidence.append({"pr": number, "base": base, "head": head,
                         "sha": sha, "draft": p["draft"], "state": status,
                         "merged_at": merged})
    return {"scope": "PR_METADATA_ONLY", "verified": not failures,
            "checks": evidence, "failures": failures,
            "not_verified": ["same-SHA frontend/backend/browser E2E",
                             "approval concurrency", "CI log integrity",
                             "production release", "broker execution"]}


def fetch_pr(number):
    url = f"https://api.github.com/repos/{REPO}/pulls/{number}"
    headers = {"Accept": "application/vnd.github+json",
               "User-Agent": "work200-pr-chain-audit"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = "Bearer " + token
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=15) as response:
        return json.load(response)


def main():
    try:
        report = check({n: fetch_pr(n) for n in CHAIN})
    except (KeyError, ValueError, OSError, urllib.error.HTTPError) as exc:
        print(json.dumps({"scope": "PR_METADATA_ONLY", "verified": False,
                          "error": str(exc)}, indent=2))
        return 2
    os.makedirs("out", exist_ok=True)
    with open("out/pr-chain-audit.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
        f.write("\n")
    print(json.dumps(report, indent=2))
    return 0 if report["verified"] else 1


if __name__ == "__main__":
    sys.exit(main())
