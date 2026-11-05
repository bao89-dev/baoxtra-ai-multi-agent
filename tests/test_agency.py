import tempfile,unittest
from pathlib import Path
from agency.council import review_charter
from agency.dag import order_tasks
from agency.core import run_pipeline
from agency.evidence import make_evidence,validate_evidence
BASE={"task_id":"T1","title":"Parser","target_repo":"org/repo","mode":"REVIEW_ONLY","acceptance_criteria":["A"],"criterion_results":[{"criterion":"A","result":"PASS"}]}
CHARTER={"project_title":"Example","owner":"owner","target_repo":"org/repo","objective":"test","acceptance_criteria":["A"],"tasks":[{"id":"a","depends_on":[]},{"id":"b","depends_on":["a"]}]}
class TestPipeline(unittest.TestCase):
    def test_no_evidence_fails_closed(self): self.assertEqual(run_pipeline(BASE)["status"],"BLOCKED")
    def test_live_blocked(self): self.assertEqual(run_pipeline({**BASE,"mode":"LIVE"})["status"],"BLOCKED")
    def test_missing_fields(self): self.assertEqual(run_pipeline({})["status"],"BLOCKED")
    def test_missing_criterion(self): self.assertEqual(run_pipeline({**BASE,"criterion_results":[]})["status"],"BLOCKED")
    def test_invalid_criterion(self): self.assertEqual(run_pipeline({**BASE,"criterion_results":[{"criterion":"A","result":"FAIL"}]})["status"],"BLOCKED")
    def test_dag_order(self): self.assertEqual(order_tasks(CHARTER["tasks"]),["a","b"])
    def test_dag_cycle_rejected(self):
        with self.assertRaises(ValueError): order_tasks([{"id":"a","depends_on":["b"]},{"id":"b","depends_on":["a"]}])
    def test_dag_unknown_rejected(self):
        with self.assertRaises(ValueError): order_tasks([{"id":"a","depends_on":["z"]}])
    def test_charter_missing(self): self.assertEqual(review_charter({})["status"],"BLOCKED_PENDING_CHARTER")
    def test_charter_planned_only(self): self.assertEqual(review_charter(CHARTER)["status"],"NEEDS_HUMAN_APPROVAL")
    def test_local_evidence_untrusted(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/"test.log";f.write_text("4 passed");e=make_evidence(BASE,f,0,"a"*40)
            self.assertIn("CI provenance not independently verified",validate_evidence(e,BASE));self.assertEqual(run_pipeline({**BASE,"evidence":e})["status"],"BLOCKED")
    def test_tampered_log_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/"test.log";f.write_text("4 passed");e=make_evidence(BASE,f,0,"a"*40);f.write_text("altered");self.assertIn("Log hash mismatch",validate_evidence(e,BASE))
    def test_wrong_task_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/"test.log";f.write_text("ok");e=make_evidence(BASE,f,0,"a"*40);e["task_id"]="other";self.assertIn("task_id mismatch",validate_evidence(e,BASE))
    def test_failing_exit_code(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/"test.log";f.write_text("FAIL");e=make_evidence(BASE,f,1,"a"*40);self.assertIn("Tests not confirmed passing",validate_evidence(e,BASE))
if __name__=="__main__":unittest.main()
