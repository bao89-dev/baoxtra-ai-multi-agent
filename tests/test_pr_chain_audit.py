import unittest
from scripts.audit_pr_chain import CHAIN, EXPECTED, check


def fixtures():
    return {
        n: {"base": {"ref": EXPECTED[n][0]},
            "head": {"ref": EXPECTED[n][1], "sha": f"{n:040x}"},
            "state": "open", "merged_at": None, "draft": True}
        for n in CHAIN
    }


class PRChainAuditTests(unittest.TestCase):
    def test_valid_chain_only_verifies_metadata(self):
        result = check(fixtures())
        self.assertTrue(result["verified"])
        self.assertIn("same-SHA frontend/backend/browser E2E", result["not_verified"])

    def test_wrong_base_fails_closed(self):
        prs = fixtures()
        prs[9]["base"]["ref"] = "main"
        self.assertFalse(check(prs)["verified"])

    def test_merged_pr_fails_closed(self):
        prs = fixtures()
        prs[10]["merged_at"] = "2026-11-08T00:00:00Z"
        self.assertFalse(check(prs)["verified"])

    def test_invalid_sha_fails_closed(self):
        prs = fixtures()
        prs[11]["head"]["sha"] = "bad"
        self.assertFalse(check(prs)["verified"])


if __name__ == "__main__":
    unittest.main()
