"""Safe V0.3 CLI — proposal only and fixed local unittest runner."""
import argparse
import json
from pathlib import Path
from agency.developer_agent import create_proposal
from agency.tester_agent import execute_unit_tests


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    p = sub.add_parser("propose")
    p.add_argument("--task", required=True)
    p.add_argument("--out", required=True)
    t = sub.add_parser("test")
    t.add_argument("--repo", required=True)
    t.add_argument("--out-dir", required=True)
    t.add_argument("--report", required=True)
    args = parser.parse_args()
    if args.action == "propose":
        data = json.loads(Path(args.task).read_text(encoding="utf-8"))
        result = create_proposal(data)
        output = Path(args.out)
    else:
        result = execute_unit_tests(args.repo, args.out_dir)
        output = Path(args.report)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result["status"] not in ("PROPOSED_REVIEW_ONLY", "LOCAL_TEST_PASS_UNTRUSTED"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
