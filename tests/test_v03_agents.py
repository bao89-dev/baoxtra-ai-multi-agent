import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from agency.developer_agent import create_proposal
from agency.tester_agent import execute_unit_tests, COMMAND

SPEC = {"task_id":"T-2","target_repo":"org/repo","base_sha":"a"*40,
        "branch":"feat/safe-change","mode":"REVIEW_ONLY",
        "changes":[{"path":"docs/design.md","operation":"modify","description":"Document contract"}]}

class TestDeveloper(unittest.TestCase):
    def test_valid_draft(self):
        p=create_proposal(SPEC)
        self.assertEqual(p["status"],"PROPOSED_REVIEW_ONLY")
        self.assertFalse(p["writes_performed"])
        self.assertFalse(p["pull_request_created"])
        self.assertTrue(p["requires_owner_review"])

    def test_live_rejected(self):
        self.assertEqual(create_proposal({**SPEC,"mode":"LIVE"})["status"],"BLOCKED")

    def test_main_branch_rejected(self):
        self.assertEqual(create_proposal({**SPEC,"branch":"main"})["status"],"BLOCKED")

    def test_bad_sha_rejected(self):
        self.assertEqual(create_proposal({**SPEC,"base_sha":"xyz"})["status"],"BLOCKED")

    def test_traversal_rejected(self):
        changes=[{"path":"docs/../../etc/passwd","operation":"add","description":"bad"}]
        self.assertEqual(create_proposal({**SPEC,"changes":changes})["status"],"BLOCKED")

    def test_workflow_edit_rejected(self):
        changes=[{"path":".github/workflows/ci.yml","operation":"modify","description":"bad"}]
        self.assertEqual(create_proposal({**SPEC,"changes":changes})["status"],"BLOCKED")

    def test_duplicate_rejected(self):
        self.assertEqual(create_proposal({**SPEC,"changes":SPEC["changes"]*2})["status"],"BLOCKED")

    def test_empty_rejected(self):
        self.assertEqual(create_proposal({**SPEC,"changes":[]})["status"],"BLOCKED")

    def test_delete_rejected(self):
        changes=[{"path":"docs/x.md","operation":"delete","description":"bad"}]
        self.assertEqual(create_proposal({**SPEC,"changes":changes})["status"],"BLOCKED")

    def test_invalid_object(self):
        self.assertEqual(create_proposal(None)["status"],"BLOCKED")

class TestTester(unittest.TestCase):
    def test_invalid_directory_rejected(self):
        with tempfile.TemporaryDirectory() as p:
            self.assertEqual(execute_unit_tests(p,p+"/log")["status"],"BLOCKED")

    def test_output_in_repo_rejected(self):
        with tempfile.TemporaryDirectory() as p:
            root=Path(p)
            (root/"agency").mkdir(); (root/"tests").mkdir()
            self.assertEqual(execute_unit_tests(root,root/"out")["status"],"BLOCKED")

    def test_timeout_configuration_rejected(self):
        with tempfile.TemporaryDirectory() as p, tempfile.TemporaryDirectory() as out:
            root=Path(p)
            (root/"agency").mkdir(); (root/"tests").mkdir()
            self.assertEqual(execute_unit_tests(root,out,timeout_seconds=0)["status"],"BLOCKED")

    def test_fixed_command_no_shell(self):
        self.assertEqual(COMMAND[1:],("-m","unittest","discover","-s","tests","-v"))

    def test_success_receipt_is_untrusted(self):
        with tempfile.TemporaryDirectory() as p, tempfile.TemporaryDirectory() as out:
            root=Path(p);(root/"agency").mkdir();(root/"tests").mkdir()
            (root/"tests"/"test_ok.py").write_text("import unittest\nclass T(unittest.TestCase):\n def test_ok(self): self.assertTrue(True)\n")
            r=execute_unit_tests(root,out)
            self.assertEqual(r["status"],"LOCAL_TEST_PASS_UNTRUSTED")
            self.assertEqual(r["exit_code"],0)
            self.assertEqual(len(r["log_sha256"]),64)

    def test_failure_receipt(self):
        with tempfile.TemporaryDirectory() as p, tempfile.TemporaryDirectory() as out:
            root=Path(p);(root/"agency").mkdir();(root/"tests").mkdir()
            (root/"tests"/"test_bad.py").write_text("import unittest\nclass T(unittest.TestCase):\n def test_bad(self): self.fail('expected')\n")
            r=execute_unit_tests(root,out)
            self.assertEqual(r["status"],"FAIL")
            self.assertNotEqual(r["exit_code"],0)
