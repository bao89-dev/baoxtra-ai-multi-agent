"""Command line interface: plan, verify, and mint LOCAL_UNTRUSTED evidence."""
import argparse,json
from pathlib import Path
from agency.core import run_pipeline
from agency.council import review_charter
from agency.evidence import make_evidence
def main():
    parser=argparse.ArgumentParser(prog="baoxtra-agency"); sub=parser.add_subparsers(dest="command",required=True)
    for name in ("plan","verify"):
        p=sub.add_parser(name);p.add_argument("--input",required=True);p.add_argument("--output",required=True)
    p=sub.add_parser("evidence");p.add_argument("--task",required=True);p.add_argument("--log",required=True);p.add_argument("--exit-code",type=int,required=True);p.add_argument("--commit",required=True);p.add_argument("--output",required=True)
    args=parser.parse_args()
    if args.command=="evidence": result=make_evidence(json.loads(Path(args.task).read_text(encoding="utf8")),args.log,args.exit_code,args.commit)
    else:
        record=json.loads(Path(args.input).read_text(encoding="utf8"));result=review_charter(record) if args.command=="plan" else run_pipeline(record)
    output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf8");print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=="__main__": main()
