"""Local evidence contract. Self-asserted GitHub provenance is never trusted."""
import hashlib
import re
from pathlib import Path

SHA_RE = re.compile(r"^[a-fA-F0-9]{40}$")


def make_evidence(task, log_path, exit_code, commit):
    log = Path(log_path)
    if not log.is_file():
        raise ValueError("Evidence log does not exist")
    if not SHA_RE.fullmatch(commit):
        raise ValueError("Commit must be a 40-character git SHA")
    if type(exit_code) is not int:
        raise ValueError("Exit code must be integer")
    return {
        "task_id": task["task_id"],
        "target_repo": task["target_repo"],
        "commit_sha": commit.lower(),
        "exit_code": exit_code,
        "result": "PASS" if exit_code == 0 else "FAIL",
        "log_path": str(log),
        "log_sha256": hashlib.sha256(log.read_bytes()).hexdigest(),
        "provenance": "LOCAL_UNTRUSTED",
        "ci_run_url": None,
    }


def validate_evidence(evidence, task):
    if not isinstance(evidence, dict):
        return ["Missing evidence object"]
    errors = []
    for field in ("task_id", "target_repo"):
        if evidence.get(field) != task.get(field):
            errors.append(field + " mismatch")
    sha = evidence.get("commit_sha", "")
    if not isinstance(sha, str) or not SHA_RE.fullmatch(sha):
        errors.append("Invalid commit SHA")
    if evidence.get("result") != "PASS" or type(evidence.get("exit_code")) is not int or evidence.get("exit_code") != 0:
        errors.append("Tests not confirmed passing")
    digest = evidence.get("log_sha256")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        errors.append("Invalid log digest")
    path = evidence.get("log_path")
    if not isinstance(path, str) or not path:
        errors.append("Missing log path")
    else:
        log = Path(path)
        if not log.is_file():
            errors.append("Log file not accessible")
        elif hashlib.sha256(log.read_bytes()).hexdigest() != digest:
            errors.append("Log hash mismatch")
    # Security: a caller can forge both provenance and ci_run_url. These are
    # NOT attested; only the read-only API metadata verifier can check GitHub.
    errors.append("CI provenance not independently verified")
    return errors
