"""Contract/security tests for review-only API."""
import os
import tempfile
import unittest
from fastapi.testclient import TestClient

class ControlAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.old_db = os.environ.get("AGENCY_DB_PATH")
        cls.old_token = os.environ.get("AGENCY_API_TOKEN")
        os.environ["AGENCY_DB_PATH"] = cls.tmp.name + "/test.sqlite3"
        os.environ["AGENCY_API_TOKEN"] = "test-token-with-24-or-more-characters"
        from agency.control_api import make_app
        cls.client = TestClient(make_app())
        cls.headers = {"Authorization": "Bearer test-token-with-24-or-more-characters"}

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        for key, previous in (("AGENCY_DB_PATH", cls.old_db), ("AGENCY_API_TOKEN", cls.old_token)):
            if previous is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = previous
        cls.tmp.cleanup()

    def create_task(self):
        r = self.client.post("/api/v1/tasks", headers=self.headers, json={
            "title": "Review BX42 parser", "module": "bx42-parser",
            "priority": "High", "request": "Run parser unit tests", "mode": "REVIEW_ONLY"})
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()["id"]

    def test_health(self):
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertIs(r.json()["live_execution"], False)

    def test_auth(self):
        self.assertEqual(self.client.get("/api/v1/tasks").status_code, 401)

    def test_live_blocked(self):
        r = self.client.post("/api/v1/tasks", headers=self.headers, json={
            "title": "Execute trade", "module": "agency-core",
            "request": "Execute live trade", "mode": "LIVE"})
        self.assertEqual(r.status_code, 422)

    def test_no_self_verification(self):
        task_id = self.create_task()
        r = self.client.post(f"/api/v1/tasks/{task_id}/evidence", headers=self.headers, json={
            "command": "python -m unittest", "exit_code": 0, "environment": "GITHUB_CI",
            "commit_sha": "a"*40, "artifact_sha256": "b"*64})
        self.assertEqual(r.status_code, 201, r.text)
        self.assertEqual(r.json()["verification"], "UNVERIFIED_SUBMISSION")
        detail = self.client.get(f"/api/v1/tasks/{task_id}", headers=self.headers).json()
        self.assertEqual(detail["status"], "NOT_RUN")
        self.assertEqual(len(detail["evidence"]), 1)
        self.assertTrue(detail["audit"])
        r = self.client.patch(f"/api/v1/tasks/{task_id}", headers=self.headers, json={"status": "VERIFIED"})
        self.assertEqual(r.status_code, 422)

    def test_filters(self):
        self.create_task()
        r = self.client.get("/api/v1/tasks?module=bx42-parser&priority=High", headers=self.headers)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(all(t["module"] == "bx42-parser" for t in r.json()["items"]))

    def test_reject_bad_digest(self):
        task_id = self.create_task()
        r = self.client.post(f"/api/v1/tasks/{task_id}/evidence", headers=self.headers,
             json={"command": "pytest", "environment": "LOCAL", "artifact_sha256": "fake"})
        self.assertEqual(r.status_code, 422)

if __name__ == "__main__":
    unittest.main()
