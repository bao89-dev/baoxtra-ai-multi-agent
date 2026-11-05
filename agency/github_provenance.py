"""Read-only GitHub Actions metadata verifier. No self-supplied PASS claims.

This verifies workflow/job/artifact metadata from GitHub's API, NOT the bytes
of the uploaded log, independent test coverage, or production readiness.
"""
import json
import os
import re
import urllib.error
import urllib.request

REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
WORKFLOW = ".github/workflows/ci.yml"
JOB = "unit-tests"
ARTIFACT = "unit-test-log"


def github_get(path, token=None, timeout=15):
    """Only fetch GitHub API endpoints constructed from validated identifiers."""
    request = urllib.request.Request(
        "https://api.github.com" + path,
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            **({"Authorization": "Bearer " + token} if token else {}),
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if response.geturl().split("/")[2] != "api.github.com":
            raise ValueError("Untrusted GitHub API redirect")
        return json.load(response)


def verify_ci_metadata(repo, commit_sha, run_id, *, fetcher=None):
    """Verify a specific CI run against the expected repo + exact commit.

    The fetcher is an injected read-only callable(path), enabling offline
    negative-case tests. A positive result is *metadata verification only*.
    """
    output = {
        "status": "BLOCKED",
        "verification_level": "CI_METADATA_ONLY",
        "repo": repo,
        "commit_sha": commit_sha,
        "run_id": run_id,
        "release_gate": "HUMAN_APPROVAL_REQUIRED",
        "live_execution": False,
        "auto_merge": False,
        "reasons": [],
    }
    if not isinstance(repo, str) or not REPO_RE.fullmatch(repo) or ".." in repo:
        output["reasons"].append("Invalid repository")
    if not isinstance(commit_sha, str) or not SHA_RE.fullmatch(commit_sha):
        output["reasons"].append("Invalid commit SHA")
    if type(run_id) is not int or run_id <= 0:
        output["reasons"].append("Invalid run ID")
    if output["reasons"]:
        return output
    expected_sha = commit_sha.lower()
    fetch = fetcher or (lambda path: github_get(path, token=os.environ.get("GITHUB_TOKEN")))
    prefix = "/repos/" + repo + "/actions/"
    try:
        run = fetch(prefix + "runs/" + str(run_id))
        jobs = fetch(prefix + "runs/" + str(run_id) + "/jobs?per_page=100")
        artifacts = fetch(prefix + "runs/" + str(run_id) + "/artifacts?per_page=100")
        if not all(isinstance(x, dict) for x in (run, jobs, artifacts)):
            raise ValueError("Invalid GitHub API response")
        checks = [
            (run.get("head_sha", "").lower() == expected_sha, "Workflow commit mismatch"),
            (run.get("repository", {}).get("full_name", "").lower() == repo.lower(), "Workflow repository mismatch"),
            (run.get("path") == WORKFLOW, "Unexpected workflow path"),
            (run.get("status") == "completed" and run.get("conclusion") == "success", "Workflow not successful"),
            (run.get("event") in ("push", "pull_request", "workflow_dispatch"), "Unexpected workflow trigger"),
        ]
        for ok, message in checks:
            if not ok:
                output["reasons"].append(message)
        job_list = jobs.get("jobs")
        if not isinstance(job_list, list) or len(job_list) != 1 or jobs.get("total_count") != 1:
            output["reasons"].append("Incomplete or ambiguous job listing")
        else:
            job = job_list[0]
            if job.get("name") != JOB or job.get("conclusion") != "success":
                output["reasons"].append("Trusted unit-test job did not succeed")
            if job.get("head_sha", "").lower() != expected_sha:
                output["reasons"].append("Job commit mismatch")
            steps = {s.get("name"): s.get("conclusion") for s in job.get("steps", []) if isinstance(s, dict)}
            for required in ("Unit tests", "Upload CI log"):
                if steps.get(required) != "success":
                    output["reasons"].append("Missing successful step: " + required)
        artifact_list = artifacts.get("artifacts")
        if not isinstance(artifact_list, list) or artifacts.get("total_count") != 1 or len(artifact_list) != 1:
            output["reasons"].append("Incomplete or ambiguous artifact listing")
        else:
            artifact = artifact_list[0]
            if artifact.get("name") != ARTIFACT or artifact.get("expired") is not False or artifact.get("size_in_bytes", 0) <= 0:
                output["reasons"].append("CI log artifact missing, expired or empty")
            workflow_ref = artifact.get("workflow_run") or {}
            if workflow_ref.get("id") != run_id or str(workflow_ref.get("head_sha", "")).lower() != expected_sha:
                output["reasons"].append("Artifact workflow identity mismatch")
            if not output["reasons"]:
                output["artifact_id"] = artifact.get("id")
        if not output["reasons"]:
            output["status"] = "CI_METADATA_VERIFIED"
            output["run_url"] = "https://github.com/" + repo + "/actions/runs/" + str(run_id)
            output["reasons"] = ["Artifact bytes, independent test coverage and release approval remain unverified"]
    except (ValueError, TypeError, KeyError, urllib.error.URLError, OSError) as exc:
        output["reasons"].append("GitHub verification failed: " + type(exc).__name__)
    return output
