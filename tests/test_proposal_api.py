"""Versioned owner approval and cycle-safe planning tests."""
import os
import tempfile
import unittest
from fastapi.testclient import TestClient

class ProposalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.keys=("AGENCY_DB_PATH","AGENCY_API_TOKEN","AGENCY_APPROVAL_TOKEN","AGENCY_UPLOAD_PATH")
        cls.prev={k:os.environ.get(k) for k in cls.keys}
        os.environ.update({
            "AGENCY_DB_PATH":cls.tmp.name+"/db.sqlite3",
            "AGENCY_API_TOKEN":"backend-token-123456789012345678901234",
            "AGENCY_APPROVAL_TOKEN":"owner-approval-secret-123456789012345678901234",
            "AGENCY_UPLOAD_PATH":cls.tmp.name+"/uploads"
        })
        from agency.control_api import make_app
        cls.client=TestClient(make_app())
        cls.headers={"Authorization":"Bearer backend-token-123456789012345678901234"}
        cls.owner={**cls.headers,"X-Owner-Approval-Key":"owner-approval-secret-123456789012345678901234"}

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        for k,v in cls.prev.items():
            if v is None: os.environ.pop(k,None)
            else: os.environ[k]=v
        cls.tmp.cleanup()

    def conversation(self):
        r=self.client.post("/api/v1/conversations",json={"title":"Application Design"},headers=self.headers)
        self.assertEqual(r.status_code,201,r.text)
        return r.json()["id"]

    def payload(self,cid):
        return {"conversation_id":cid,"title":"Application proposal",
                "summary":"Architecture proposal for an isolated task workspace.",
                "diagram":"flowchart TD; A[UI] --> B[API]",
                "tasks":[{"id":"T01","title":"Implement API","depends_on":[]},
                         {"id":"T02","title":"Verify API tests","depends_on":["T01"]}]}

    def proposal(self):
        cid=self.conversation()
        r=self.client.post("/api/v1/proposals",json=self.payload(cid),headers=self.headers)
        self.assertEqual(r.status_code,201,r.text)
        return cid,r.json()

    def decide(self,p,headers=None,version=None,sha=None,action="APPROVE"):
        return self.client.post(f"/api/v1/proposals/{p['id']}/decision",
            headers=headers or self.owner,
            json={"expected_version":version or p["version"],
                  "expected_sha256":sha or p["sha256"],"action":action,
                  "reason":"Owner reviewed this exact version"})

    def test_draft_created_and_listed(self):
        cid,p=self.proposal()
        self.assertEqual(p["status"],"DRAFT")
        detail=self.client.get("/api/v1/proposals/"+p["id"],headers=self.headers).json()
        self.assertEqual(detail["sha256"],p["sha256"])
        self.assertEqual(detail["execution"],"NOT_AUTHORIZED_BY_THIS_SERVICE")
        listed=self.client.get(f"/api/v1/conversations/{cid}/proposals",headers=self.headers).json()
        self.assertTrue(any(x["id"]==p["id"] for x in listed["items"]))

    def test_reject_cycle(self):
        cid=self.conversation()
        payload=self.payload(cid)
        payload["tasks"][0]["depends_on"]=["T02"]
        self.assertEqual(self.client.post("/api/v1/proposals",headers=self.headers,json=payload).status_code,422)

    def test_reject_unknown_dependency(self):
        cid=self.conversation()
        payload=self.payload(cid)
        payload["tasks"][1]["depends_on"]=["UNKNOWN"]
        self.assertEqual(self.client.post("/api/v1/proposals",headers=self.headers,json=payload).status_code,422)

    def test_approval_requires_distinct_credential(self):
        _,p=self.proposal()
        self.assertEqual(self.decide(p,headers=self.headers).status_code,403)
        self.assertEqual(self.decide(p).status_code,200)
        self.assertEqual(self.decide(p).status_code,409)

    def test_wrong_hash_fails_closed(self):
        _,p=self.proposal()
        self.assertEqual(self.decide(p,sha="0"*64).status_code,409)
        self.assertEqual(self.client.get("/api/v1/proposals/"+p["id"],headers=self.headers).json()["status"],"DRAFT")

    def test_revision_invalidates_previous_approval(self):
        _,p=self.proposal()
        self.assertEqual(self.decide(p).status_code,200)
        revision=self.payload(self.conversation())
        revision.pop("conversation_id")
        revision["summary"]="Architecture proposal revision with a longer approved implementation scope."
        revision["expected_version"]=1
        r=self.client.post("/api/v1/proposals/"+p["id"]+"/revisions",headers=self.headers,json=revision)
        self.assertEqual(r.status_code,201,r.text)
        self.assertEqual(r.json()["version"],2)
        self.assertEqual(self.decide(p).status_code,409)
        latest=self.client.get("/api/v1/proposals/"+p["id"],headers=self.headers).json()
        self.assertEqual(latest["status"],"DRAFT")
        self.assertIsNone(latest["decision"])
        self.assertEqual(self.decide(r.json()).status_code,200)

    def test_stale_revision_rejected(self):
        _,p=self.proposal()
        revision=self.payload(self.conversation())
        revision.pop("conversation_id")
        revision["expected_version"]=5
        self.assertEqual(self.client.post(f"/api/v1/proposals/{p['id']}/revisions",
                                          headers=self.headers,json=revision).status_code,409)

    def test_reject_and_request_changes_not_approval(self):
        for action in ("REJECT","REQUEST_CHANGES"):
            _,p=self.proposal()
            r=self.decide(p,action=action)
            self.assertEqual(r.status_code,200)
            self.assertEqual(r.json()["status"],action)
            self.assertEqual(r.json()["execution"],"NOT_AUTHORIZED_BY_THIS_SERVICE")

    def test_no_executor_or_auto_merge(self):
        _,p=self.proposal()
        self.assertEqual(self.client.post(f"/api/v1/proposals/{p['id']}/execute",
            headers=self.owner).status_code,404)
        self.assertEqual(self.client.get("/api/v1/proposals/"+p["id"],
            headers=self.headers).json()["status"],"DRAFT")

if __name__=="__main__":
    unittest.main()
