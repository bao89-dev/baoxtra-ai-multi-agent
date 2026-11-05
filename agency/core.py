"""Fail closed verifier: no code path enables live execution or auto merge."""
from agency.evidence import validate_evidence
ALLOWED_MODES={"REVIEW_ONLY","PAPER"}
def run_pipeline(task):
    if not isinstance(task,dict): return {"status":"BLOCKED","reasons":["Invalid task"]}
    required=("task_id","title","target_repo","mode","acceptance_criteria")
    missing=[k for k in required if not task.get(k)]
    if missing: return {"status":"BLOCKED","reasons":["Missing: "+", ".join(missing)]}
    if task["mode"] not in ALLOWED_MODES: return {"status":"BLOCKED","reasons":["Forbidden mode"]}
    criteria=task["acceptance_criteria"]
    if not isinstance(criteria,list) or not criteria or any(not isinstance(x,str) or not x.strip() for x in criteria): return {"status":"BLOCKED","reasons":["Invalid acceptance criteria"]}
    coverage=task.get("criterion_results")
    if not isinstance(coverage,list) or set(criteria)!=set(x.get("criterion") for x in coverage if isinstance(x,dict)) or any(not isinstance(x,dict) or x.get("result")!="PASS" for x in coverage):
        return {"status":"BLOCKED","reasons":["Acceptance criteria not independently covered"],"live_execution":False,"auto_merge":False}
    errors=validate_evidence(task.get("evidence"),task)
    return {"task_id":task["task_id"],"target_repo":task["target_repo"],"status":"REVIEW_REQUIRED" if not errors else "BLOCKED","reasons":errors,"verifier":"EVIDENCE_PRESENT_REQUIRES_HUMAN_SIGNOFF" if not errors else "EVIDENCE_REJECTED","release_gate":"HUMAN_APPROVAL_REQUIRED","live_execution":False,"auto_merge":False}
