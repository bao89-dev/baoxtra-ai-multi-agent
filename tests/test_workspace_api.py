"""Workspace API tests: isolation, attachments, event cursors, and safe semantics."""
import os
import tempfile
import unittest
from fastapi.testclient import TestClient

class WorkspaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.prior={key:os.getenv(key) for key in ("AGENCY_DB_PATH","AGENCY_API_TOKEN","AGENCY_UPLOAD_PATH")}
        os.environ["AGENCY_DB_PATH"]=cls.tmp.name+"/db.sqlite3"
        os.environ["AGENCY_UPLOAD_PATH"]=cls.tmp.name+"/quarantine"
        os.environ["AGENCY_API_TOKEN"]="test-token-for-workspace-safety-123456"
        from agency.control_api import make_app
        cls.client=TestClient(make_app())
        cls.headers={"Authorization":"Bearer test-token-for-workspace-safety-123456"}

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        for key,v in cls.prior.items():
            if v is None: os.environ.pop(key,None)
            else: os.environ[key]=v
        cls.tmp.cleanup()

    def new_chat(self):
        r=self.client.post("/api/v1/conversations",json={"title":"New application brief"},headers=self.headers)
        self.assertEqual(r.status_code,201,r.text)
        return r.json()["id"]

    def test_requires_token(self):
        self.assertEqual(self.client.get("/api/v1/conversations").status_code,401)

    def test_message_history(self):
        cid=self.new_chat()
        p=self.client.post(f"/api/v1/conversations/{cid}/messages",headers=self.headers,json={"text":"Sketch an app"})
        self.assertEqual(p.status_code,201,p.text)
        self.assertEqual(p.json()["ai_response"],"NOT_IMPLEMENTED")
        r=self.client.get(f"/api/v1/conversations/{cid}/messages",headers=self.headers)
        self.assertEqual(len(r.json()["items"]),1)

    def test_sse_event_replay(self):
        cid=self.new_chat()
        r=self.client.get(f"/api/v1/conversations/{cid}/events?once=true",headers=self.headers)
        self.assertEqual(r.status_code,200)
        self.assertIn("event: conversation.created",r.text)
        self.assertIn("id: ",r.text)
        first=int(r.text.split("id: ")[1].splitlines()[0])
        x=self.client.get(f"/api/v1/conversations/{cid}/events?once=true",headers={**self.headers,"Last-Event-ID":str(first)})
        self.assertNotIn("conversation.created",x.text)

    def test_image_quarantined_and_bound(self):
        cid=self.new_chat()
        png=b"\\x89PNG\\r\\n\\x1a\\n"+b"example-payload"
        r=self.client.post(f"/api/v1/conversations/{cid}/attachments",headers=self.headers,files={"file":("test.png",png,"image/png")})
        self.assertEqual(r.status_code,201,r.text)
        self.assertEqual(r.json()["status"],"QUARANTINED_NOT_SCANNED")
        aid=r.json()["id"]
        m=self.client.post(f"/api/v1/conversations/{cid}/messages",headers=self.headers,json={"text":"Review image","attachment_ids":[aid]})
        self.assertEqual(m.status_code,201,m.text)
        reuse=self.client.post(f"/api/v1/conversations/{cid}/messages",headers=self.headers,json={"text":"Reuse image","attachment_ids":[aid]})
        self.assertEqual(reuse.status_code,422)

    def test_reject_false_mime(self):
        cid=self.new_chat()
        r=self.client.post(f"/api/v1/conversations/{cid}/attachments",headers=self.headers,files={"file":("fake.png",b"this is not png","image/png")})
        self.assertEqual(r.status_code,415)

    def test_invalid_cross_conversation_attachment(self):
        cid1=self.new_chat()
        cid2=self.new_chat()
        png=b"\\x89PNG\\r\\n\\x1a\\n"+b"payload"
        a=self.client.post(f"/api/v1/conversations/{cid1}/attachments",headers=self.headers,files={"file":("x.png",png,"image/png")})
        self.assertEqual(a.status_code,201,a.text)
        r=self.client.post(f"/api/v1/conversations/{cid2}/messages",headers=self.headers,json={"text":"Steal","attachment_ids":[a.json()["id"]]})
        self.assertEqual(r.status_code,422)

    def test_mp4_quarantined_not_processed(self):
        cid=self.new_chat()
        mp4=b"\\x00\\x00\\x00\\x18ftypisom"+b"fake video content"
        r=self.client.post(f"/api/v1/conversations/{cid}/attachments",headers=self.headers,files={"file":("clip.mp4",mp4,"video/mp4")})
        self.assertEqual(r.status_code,201,r.text)
        self.assertEqual(r.json()["analysis"],"NOT_RUN")

if __name__=="__main__":
    unittest.main()
