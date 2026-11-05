"""V0.3 Developer planner: produces a read-only draft change proposal.

No LLM, network, shell, repository mutation, or automatic PR creation.
"""
import hashlib
import json
import re
from pathlib import PurePosixPath

SHA = re.compile(r"^[0-9a-fA-F]{40}$")
TASK = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def create_proposal(spec):
    result = {"status": "BLOCKED", "kind": "DEVELOPER_PROPOSAL",
              "requires_owner_review": True, "writes_performed": False,
              "pull_request_created": False, "live_execution": False,
              "reasons": []}
    if not isinstance(spec, dict):
        result["reasons"].append("Invalid specification")
        return result
    task_id, repo, base = (spec.get(k) for k in ("task_id", "target_repo", "base_sha"))
    if not isinstance(task_id, str) or not TASK.fullmatch(task_id):
        result["reasons"].append("Invalid task_id")
    if not isinstance(repo, str) or not REPO.fullmatch(repo) or ".." in repo:
        result["reasons"].append("Invalid target_repo")
    if not isinstance(base, str) or not SHA.fullmatch(base):
        result["reasons"].append("Invalid base_sha")
    if spec.get("mode") not in ("REVIEW_ONLY", "PAPER"):
        result["reasons"].append("Forbidden mode")
    if spec.get("branch") in (None, "", "main", "master") or not str(spec.get("branch", "")).startswith("feat/"):
        result["reasons"].append("Feature branch required")
    changes = spec.get("changes")
    if not isinstance(changes, list) or not changes:
        result["reasons"].append("Missing changes")
    else:
        paths = []
        for item in changes:
            if not isinstance(item, dict):
                result["reasons"].append("Invalid change")
                continue
            path = item.get("path")
            if not isinstance(path, str):
                result["reasons"].append("Invalid path")
                continue
            p = PurePosixPath(path)
            if (not path or path.startswith("/") or "\\" in path or
                ".." in p.parts or "." in p.parts or
                p.parts[0] not in ("agency", "tests", "docs", "examples") or
                p.suffix not in (".py", ".md", ".json") or
                any(part.startswith(".") for part in p.parts)):
                result["reasons"].append("Unsafe path")
            paths.append(path)
            if item.get("operation") not in ("add", "modify"):
                result["reasons"].append("Forbidden operation")
            if not isinstance(item.get("description"), str) or not item["description"].strip():
                result["reasons"].append("Missing description")
        if len(set(paths)) != len(paths):
            result["reasons"].append("Duplicate paths")
    if result["reasons"]:
        return result
    normalized = {k: spec[k] for k in ("task_id", "target_repo", "base_sha", "branch", "mode", "changes")}
    payload = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    result.update(status="PROPOSED_REVIEW_ONLY",task_id=task_id,target_repo=repo,
                  base_sha=base.lower(),branch=spec["branch"],changes=changes,
                  proposal_sha256=hashlib.sha256(payload).hexdigest())
    return result
