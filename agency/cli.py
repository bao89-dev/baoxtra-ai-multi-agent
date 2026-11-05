"""Command line interface: plan, verify, local evidence, GitHub CI metadata."""
import argparse
import json
from pathlib import Path
from agency.core import run_pipeline
from agency.council import review_charter
from agency.evidence import make_evidence
from agency.github_provenance import verify_ci_metadata


def main():
    parser = argparse.ArgumentParser(prog="baoxtra-agency")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("plan", "verify"):
        p = sub.add_parser(name)
        p.add_argument("--input", required=True)
        p.add_argument("--output", required=True)
    p = sub.add_parser("evidence")
    p.add_argument("--task", required=True)
    p.add_argument("--log", required=True)
    p.add_argument("--exit-code", type=int, required=True)
    p.add_argument("--commit", required=True)
    p.add_argument("--output", required=True)
    p = sub.add_parser("verify-ci")
    p.add_argument("--repo", required=True)
    p.add_argument("--commit", required=True)
    p.add_argument("--run-id", type=int, required=True)
    p.add_argument("--output", required=True)
    args = parser.parse_args()

    if args.command == "evidence":
        task = json.loads(Path(args.task).read_text(encoding="utf8"))
        result = make_evidence(task, args.log, args.exit_code, args.commit)
    elif args.command == "verify-ci":
        result = verify_ci_metadata(args.repo, args.commit, args.run_id)
    else:
        record = json.loads(Path(args.input).read_text(encoding="utf8"))
        result = review_charter(record) if args.command == "plan" else run_pipeline(record)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.command == "verify-ci" and result["status"] != "CI_METADATA_VERIFIED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
