import copy
import unittest
from agency.github_provenance import verify_ci_metadata

REPO = "bao89-dev/baoxtra-ai-multi-agent"
SHA = "a" * 40
RUN_ID = 12345

def fixtures():
    return {
        "runs/": {
            "head_sha": SHA, "repository": {"full_name": REPO},
            "path": ".github/workflows/ci.yml", "status": "completed",
            "conclusion": "success", "event": "pull_request",
        },
        "jobs": {
            "total_count": 1,
            "jobs": [{"name": "unit-tests", "conclusion": "success",
                      "head_sha": SHA, "steps": [
                          {"name": "Unit tests", "conclusion": "success"},
                          {"name": "Upload CI log", "conclusion": "success"},
                      ]}],
        },
        "artifacts": {
            "total_count": 1, "artifacts": [{
                "id": 44, "name": "unit-test-log", "expired": False,
                "size_in_bytes": 100, "workflow_run": {"id": RUN_ID, "head_sha": SHA}
            }],
        },
    }

def check(data=None, sha=SHA, run_id=RUN_ID, repo=REPO):
    data = data or fixtures()
    def fake_fetch(path):
        if path.endswith("/jobs?per_page=100"): return data["jobs"]
        if path.endswith("/artifacts?per_page=100"): return data["artifacts"]
        if path.endswith("/runs/" + str(RUN_ID)): return data["runs/"]
        raise ValueError("Unknown path")
    return verify_ci_metadata(repo, sha, run_id, fetcher=fake_fetch)

class TestGitHubProvenance(unittest.TestCase):
    def test_success_metadata_only(self):
        result = check()
        self.assertEqual(result["status"], "CI_METADATA_VERIFIED")
        self.assertEqual(result["artifact_id"], 44)
        self.assertEqual(result["release_gate"], "HUMAN_APPROVAL_REQUIRED")
        self.assertFalse(result["live_execution"])
        self.assertFalse(result["auto_merge"])

    def test_invalid_repo(self):
        self.assertEqual(check(repo="../etc/passwd")["status"], "BLOCKED")

    def test_invalid_sha(self):
        self.assertEqual(check(sha="short")["status"], "BLOCKED")

    def test_invalid_run_id(self):
        self.assertEqual(check(run_id=True)["status"], "BLOCKED")

    def test_wrong_commit(self):
        data = fixtures(); data["runs/"]["head_sha"] = "b" * 40
        self.assertEqual(check(data)["status"], "BLOCKED")

    def test_wrong_repository(self):
        data = fixtures(); data["runs/"]["repository"]["full_name"] = "other/repo"
        self.assertEqual(check(data)["status"], "BLOCKED")

    def test_failed_workflow(self):
        data = fixtures(); data["runs/"]["conclusion"] = "failure"
        self.assertEqual(check(data)["status"], "BLOCKED")

    def test_pending_workflow(self):
        data = fixtures(); data["runs/"]["status"] = "in_progress"
        self.assertEqual(check(data)["status"], "BLOCKED")

    def test_wrong_workflow(self):
        data = fixtures(); data["runs/"]["path"] = ".github/workflows/untrusted.yml"
        self.assertEqual(check(data)["status"], "BLOCKED")

    def test_failed_job(self):
        data = fixtures(); data["jobs"]["jobs"][0]["conclusion"] = "failure"
        self.assertEqual(check(data)["status"], "BLOCKED")

    def test_missing_upload_step(self):
        data = fixtures(); data["jobs"]["jobs"][0]["steps"].pop()
        self.assertEqual(check(data)["status"], "BLOCKED")

    def test_expired_artifact(self):
        data = fixtures(); data["artifacts"]["artifacts"][0]["expired"] = True
        self.assertEqual(check(data)["status"], "BLOCKED")

    def test_wrong_artifact_commit(self):
        data = fixtures(); data["artifacts"]["artifacts"][0]["workflow_run"]["head_sha"] = "b" * 40
        self.assertEqual(check(data)["status"], "BLOCKED")

    def test_paginated_jobs_are_not_trusted(self):
        data = fixtures(); data["jobs"]["total_count"] = 101
        self.assertEqual(check(data)["status"], "BLOCKED")

    def test_paginated_artifacts_are_not_trusted(self):
        data = fixtures(); data["artifacts"]["total_count"] = 101
        self.assertEqual(check(data)["status"], "BLOCKED")

    def test_network_failure_fails_closed(self):
        def boom(path): raise OSError("offline")
        self.assertEqual(verify_ci_metadata(REPO, SHA, RUN_ID, fetcher=boom)["status"], "BLOCKED")

if __name__ == "__main__":
    unittest.main()
