"""Deterministic task graph; unknown dependencies and cycles are rejected."""
def order_tasks(tasks):
    if not isinstance(tasks,list) or not tasks: raise ValueError("Tasks must be a nonempty list")
    if any(not isinstance(t,dict) or not isinstance(t.get("id"),str) or not t["id"] for t in tasks): raise ValueError("Invalid task id")
    ids=[t["id"] for t in tasks]
    if len(set(ids))!=len(ids): raise ValueError("Duplicate task id")
    pending={t["id"]:set(t.get("depends_on",[])) for t in tasks}
    if any(not deps.issubset(pending.keys()) for deps in pending.values()): raise ValueError("Unknown dependency")
    result=[]
    while pending:
        ready=sorted(k for k,deps in pending.items() if not deps)
        if not ready: raise ValueError("Circular dependencies")
        for key in ready: result.append(key); del pending[key]
        for deps in pending.values(): deps.difference_update(ready)
    return result
