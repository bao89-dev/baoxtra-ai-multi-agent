import os
import tempfile
import unittest
from fastapi.testclient import TestClient

class BudgetGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.keys=("AGENCY_DB_PATH","AGENCY_API_TOKEN","AGENCY_PAID_OPERATIONS_ENABLED",
                  "AGENCY_DAILY_BUDGET_USD","AGENCY_TASK_BUDGET_USD")
        cls.prev={key:os.environ.get(key) for key in cls.keys}
        os.environ["AGENCY_DB_PATH"]=cls.tmp.name+"/db.sqlite3"
        os.environ["AGENCY_API_TOKEN"]="budget-test-token-with-minimum-length-123"
        os.environ["AGENCY_PAID_OPERATIONS_ENABLED"]="false"
        os.environ["AGENCY_DAILY_BUDGET_USD"]="0"
        os.environ["AGENCY_TASK_BUDGET_USD"]="0"
        from agency.control_api import make_app
        cls.client=TestClient(make_app())
        cls.headers={"Authorization":"Bearer budget-test-token-with-minimum-length-123"}

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        for key,val in cls.prev.items():
            if val is None: os.environ.pop(key,None)
            else: os.environ[key]=val
        cls.tmp.cleanup()

    def reserve(self, amount="0.50", key="request-reference-0001"):
        return self.client.post("/api/v1/cost-reservations",headers=self.headers,
            json={"task_id":"TEST-001","max_cost_usd":amount,"category":"LLM","idempotency_key":key})

    def test_zero_cost_default_policy(self):
        policy=self.client.get("/api/v1/cost-policy",headers=self.headers).json()
        self.assertFalse(policy["enabled"])
        self.assertEqual(policy["daily_limit_usd"],"0")
        self.assertFalse(policy["charging_enabled_by_this_endpoint"])
        self.assertEqual(self.reserve().status_code,403)

    def test_auth(self):
        self.assertEqual(self.client.get("/api/v1/cost-policy").status_code,401)

    def test_reservation_bounded_and_idempotent(self):
        os.environ["AGENCY_PAID_OPERATIONS_ENABLED"]="true"
        os.environ["AGENCY_DAILY_BUDGET_USD"]="1.00"
        os.environ["AGENCY_TASK_BUDGET_USD"]="0.60"
        try:
            r=self.reserve("0.50","request-reference-0101")
            self.assertEqual(r.status_code,201,r.text)
            self.assertFalse(r.json()["external_call_executed"])
            same=self.reserve("0.50","request-reference-0101")
            self.assertEqual(same.status_code,201,same.text)
            self.assertTrue(same.json()["idempotent"])
            self.assertEqual(self.reserve("0.70","request-reference-0102").status_code,403)
            self.assertEqual(self.reserve("0.60","request-reference-0103").status_code,403)
            self.assertEqual(self.reserve("0.50","request-reference-0101").status_code,201)
        finally:
            os.environ["AGENCY_PAID_OPERATIONS_ENABLED"]="false"
            os.environ["AGENCY_DAILY_BUDGET_USD"]="0"
            os.environ["AGENCY_TASK_BUDGET_USD"]="0"

    def test_invalid_amount(self):
        os.environ["AGENCY_PAID_OPERATIONS_ENABLED"]="true"
        os.environ["AGENCY_DAILY_BUDGET_USD"]="2.00"
        os.environ["AGENCY_TASK_BUDGET_USD"]="2.00"
        try:
            for invalid in ("-1","NaN","1.123","Infinity","cat"):
                self.assertEqual(self.reserve(invalid, "request-invalid-0001").status_code,422)
        finally:
            os.environ["AGENCY_PAID_OPERATIONS_ENABLED"]="false"
            os.environ["AGENCY_DAILY_BUDGET_USD"]="0"
            os.environ["AGENCY_TASK_BUDGET_USD"]="0"

if __name__=="__main__":
    unittest.main()
