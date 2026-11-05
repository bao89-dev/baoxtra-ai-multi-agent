"""Charter contract gate. Actual AI Council/LLM is NOT integrated."""
from agency.dag import order_tasks
REQUIRED=("project_title","owner","target_repo","objective","acceptance_criteria","tasks")
def review_charter(charter):
    if not isinstance(charter,dict): return {"status":"BLOCKED_PENDING_CHARTER","reasons":["Invalid charter"]}
    missing=[field for field in REQUIRED if not charter.get(field)]
    if missing: return {"status":"BLOCKED_PENDING_CHARTER","reasons":["Missing: "+", ".join(missing)]}
    criteria=charter["acceptance_criteria"]
    if not isinstance(criteria,list) or not criteria or any(not isinstance(x,str) or not x.strip() for x in criteria): return {"status":"BLOCKED_PENDING_CHARTER","reasons":["Invalid acceptance criteria"]}
    try: ordering=order_tasks(charter["tasks"])
    except (ValueError,TypeError) as exc: return {"status":"BLOCKED_PENDING_CHARTER","reasons":[str(exc)]}
    return {"status":"NEEDS_HUMAN_APPROVAL","council":"NOT_EXECUTED","planned_order":ordering,"target_repo":charter["target_repo"],"live_execution":False,"auto_merge":False}
