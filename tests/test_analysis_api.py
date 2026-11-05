"""V0.7 fail-closed analysis jobs: no unsafe file interpretation or fake AI PASS."""
import os
import tempfile
import unittest

from fastapi.testclient import TestClient

class AnalysisJobsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.before = {key: os.getenv(key) for key in ("AGENCY_DB_PATH","AGENCY_API_TOKEN","AGENCY_UPLOAD_PATH")}
        os.environ["AGENCY_DB_PATH"] = cls.temp.name + "/db.sqlite3"
        os.environ["AGENCY_UPLOAD_PATH"] = cls.temp.name + "/files"
        os.environ["AGENCY_API_TOKEN"] = "a-secure-test-token-for-v07-only"
        from agency.control_api import make_app
        cls.app = TestClient(make_app())
        cls.headers = {"Authorization": "Bearer a-secure-test-token-for-v07-only"}

    @classmethod
    def tearDownClass(cls):
        cls.app.close()
        for key, value in cls.before.items():
            if value is None: os.environ.pop(key,None)
            else: os.environ[key] = value
        cls.temp.cleanup()

    def conversation(self):
        r=self.app.post("/api/v1/conversations",headers=self.headers,json={"title":"Vision review test"})
        self.assertEqual(r.status_code,201,r.text)
        return r.json()["id"]

    def upload(self,cid,kind="image"):
        if kind=="image":
            fixture=b"\x89PNG\r\n\x1a\n"+"test".encode()
            name,mime="screen.png","image/png"
        else:
            fixture=b"\x00\x00\x00\x18ftypisom"+"movie".encode()
            name,mime="movie.mp4","video/mp4"
        r=self.app.post(f"/api/v1/conversations/{cid}/attachments",headers=self.headers,
            files={"file":(name,fixture,mime)})
        self.assertEqual(r.status_code,201,r.text)
        return r.json()["id"]

    def test_auth_required(self):
        self.assertEqual(self.app.get("/api/v1/analysis-jobs/anything").status_code,401)

    def test_blocked_job_never_claims_analysis(self):
        cid=self.conversation()
        aid=self.upload(cid)
        r=self.app.post(f"/api/v1/conversations/{cid}/analysis-jobs",headers=self.headers,
            json={"attachment_id":aid,"job_type":"image_review","instructions":"Extract UI"})
        self.assertEqual(r.status_code,201,r.text)
        result=r.json()
        self.assertEqual(result["status"],"BLOCKED_SECURITY")
        self.assertFalse(result["model_executed"])
        self.assertIsNone(result["result_summary"])
        d=self.app.get("/api/v1/analysis-jobs/"+result["id"],headers=self.headers)
        self.assertEqual(d.status_code,200)
        self.assertEqual(d.json()["status"],"BLOCKED_SECURITY")
        self.assertIsNone(d.json()["result_json"])
        listing=self.app.get(f"/api/v1/conversations/{cid}/analysis-jobs",headers=self.headers)
        self.assertIn(result["id"],[x["id"] for x in listing.json()["items"]])
        event=self.app.get(f"/api/v1/conversations/{cid}/events?once=true",headers=self.headers)
        self.assertIn("event: analysis.blocked",event.text)

    def test_cross_conversation_attachment_rejected(self):
        a,b=self.conversation(),self.conversation()
        aid=self.upload(a)
        r=self.app.post(f"/api/v1/conversations/{b}/analysis-jobs",headers=self.headers,
            json={"attachment_id":aid,"job_type":"image_review"})
        self.assertEqual(r.status_code,404)

    def test_mismatch_image_video_rejected(self):
        cid=self.conversation()
        aid=self.upload(cid)
        r=self.app.post(f"/api/v1/conversations/{cid}/analysis-jobs",headers=self.headers,
            json={"attachment_id":aid,"job_type":"video_review"})
        self.assertEqual(r.status_code,422)

    def test_video_stays_blocked(self):
        cid=self.conversation()
        aid=self.upload(cid,"video")
        r=self.app.post(f"/api/v1/conversations/{cid}/analysis-jobs",headers=self.headers,
            json={"attachment_id":aid,"job_type":"video_review"})
        self.assertEqual(r.status_code,201,r.text)
        self.assertEqual(r.json()["status"],"BLOCKED_SECURITY")

    def test_no_public_execution_or_update_route(self):
        cid=self.conversation()
        aid=self.upload(cid)
        r=self.app.post(f"/api/v1/conversations/{cid}/analysis-jobs",headers=self.headers,
            json={"attachment_id":aid,"job_type":"image_review"})
        job_id=r.json()["id"]
        self.assertEqual(self.app.patch("/api/v1/analysis-jobs/"+job_id,
            headers=self.headers,json={"status":"COMPLETED"}).status_code,405)
        self.assertEqual(self.app.post("/api/v1/analysis-jobs/"+job_id+"/run",
            headers=self.headers).status_code,404)

if __name__ == "__main__":
    unittest.main()
