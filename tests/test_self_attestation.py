import tempfile
import unittest
from pathlib import Path
from agency.evidence import make_evidence, validate_evidence
from agency.core import run_pipeline
BASE={"task_id":"T1","title":"Parser","target_repo":"org/repo","mode":"REVIEW_ONLY",
      "acceptance_criteria":["A"],"criterion_results":[{"criterion":"A","result":"PASS"}]}
class TestNoSelfAttestation(unittest.TestCase):
    def test_spoofed_git_hub_provenance_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/"log.txt"
            f.write_text("Ran 14 tests OK")
            evidence=make_evidence(BASE,f,0,"a"*40)
            evidence["provenance"]="GITHUB_ACTIONS_VERIFIED"
            evidence["ci_run_url"]="https://github.com/org/repo/actions/runs/123"
            self.assertIn("CI provenance not independently verified",
                          validate_evidence(evidence,BASE))
            self.assertEqual(run_pipeline({**BASE,"evidence":evidence})["status"],"BLOCKED")
