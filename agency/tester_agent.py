"""V0.3 constrained test runner. Process separation is NOT a security sandbox.

Runs the repository's fixed unittest suite, not arbitrary supplied commands.
Only use with trusted, checked-out repository code in a separate CI runner.
"""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import time

COMMAND = (sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v")


def execute_unit_tests(repo_root, output_dir, timeout_seconds=120):
    result = {"status": "BLOCKED", "mode": "REVIEW_ONLY", "live_execution": False,
              "shell": False, "command": list(COMMAND), "exit_code": None,
              "log_path": None, "log_sha256": None, "reasons": []}
    root = Path(repo_root).resolve()
    output = Path(output_dir).resolve()
    if not (root.is_dir() and (root / "agency").is_dir() and (root / "tests").is_dir()):
        result["reasons"].append("Not a checked-out agency repository")
        return result
    if not isinstance(timeout_seconds, int) or isinstance(timeout_seconds, bool) or not 1 <= timeout_seconds <= 300:
        result["reasons"].append("Invalid timeout")
        return result
    if output == root or root in output.parents:
        result["reasons"].append("Evidence output must be outside the repository")
        return result
    if output.exists() and output.is_symlink():
        result["reasons"].append("Symlink output rejected")
        return result
    output.mkdir(parents=True, exist_ok=True)
    log = output / "unittest.log"
    started = time.monotonic()
    try:
        completed = subprocess.run(COMMAND, cwd=root, shell=False,
                                   capture_output=True, timeout=timeout_seconds,
                                   env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        content = completed.stdout + b"\n" + completed.stderr
        code = completed.returncode
    except subprocess.TimeoutExpired as exc:
        content = (exc.stdout or b"") + b"\n" + (exc.stderr or b"") + b"\nTIMEOUT"
        code = 124
        result["reasons"].append("Unit-test timeout")
    log.write_bytes(content)
    result.update(exit_code=code, log_path=str(log),
                  log_sha256=hashlib.sha256(content).hexdigest(),
                  elapsed_ms=round((time.monotonic() - started) * 1000),
                  status="LOCAL_TEST_PASS_UNTRUSTED" if code == 0 else "FAIL")
    if code != 0 and not result["reasons"]:
        result["reasons"].append("Unit tests exited nonzero")
    return result
