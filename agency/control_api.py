"""Review-first API for agency dashboard. No agent, CI, or trading execution."""
import hmac
import json
import os
import re
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, Depends, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

STATUSES = ("NOT_RUN", "BLOCKED", "FAIL", "VERIFIED")
MODULE = Literal["core-pytest", "bx42-parser", "paper-e2e", "dashboard-api", "mt5-v0.1", "agency-core"]

def now():
    return datetime.now(timezone.utc).isoformat()

@contextmanager
def database():
    path = Path(os.getenv("AGENCY_DB_PATH", "./out/control-api.sqlite3"))
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    try:
        with db:
            yield db
    finally:
        db.close()

def initialize():
    with database() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY, title TEXT NOT NULL, module TEXT NOT NULL,
            priority TEXT NOT NULL, request TEXT NOT NULL, mode TEXT NOT NULL,
            status TEXT NOT NULL, branch TEXT, commit_sha TEXT,
            blocker TEXT, next_step TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
        db.execute("""CREATE TABLE IF NOT EXISTS evidence (
            id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(id),
            command TEXT NOT NULL, exit_code INTEGER, log_url TEXT,
            artifact_sha256 TEXT, commit_sha TEXT, environment TEXT NOT NULL,
            verified_by TEXT, verification_note TEXT NOT NULL, created_at TEXT NOT NULL)""")
        db.execute("""CREATE TABLE IF NOT EXISTS audit (
            id TEXT PRIMARY KEY, task_id TEXT NOT NULL, event TEXT NOT NULL,
            payload TEXT NOT NULL, created_at TEXT NOT NULL)""")

def auth(authorization: str | None = Header(default=None)):
    token = os.getenv("AGENCY_API_TOKEN", "")
    if len(token) < 24:
        raise HTTPException(503, "API token not configured")
    if not authorization or not hmac.compare_digest(authorization, "Bearer " + token):
        raise HTTPException(401, "Invalid credentials")

class TaskCreate(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    module: MODULE
    priority: Literal["High", "Medium", "Low"] = "Medium"
    request: str = Field(min_length=5, max_length=8000)
    mode: Literal["REVIEW_ONLY", "PAPER"] = "REVIEW_ONLY"

class TaskUpdate(BaseModel):
    status: Literal["NOT_RUN", "BLOCKED", "FAIL"] | None = None
    branch: str | None = Field(default=None, max_length=200)
    commit_sha: str | None = None
    blocker: str | None = Field(default=None, max_length=2000)
    next_step: str | None = Field(default=None, max_length=2000)

    @field_validator("commit_sha")
    @classmethod
    def validate_commit(cls, v):
        if v is not None and not re.fullmatch(r"[0-9a-f]{40}", v):
            raise ValueError("commit SHA must be 40 lowercase hexadecimal characters")
        return v

class EvidenceCreate(BaseModel):
    command: str = Field(min_length=1, max_length=1000)
    exit_code: int | None = None
    log_url: str | None = Field(default=None, max_length=2000)
    artifact_sha256: str | None = None
    commit_sha: str | None = None
    environment: Literal["GITHUB_CI", "SANDBOX", "BROWSER", "MT5", "LOCAL"]

    @field_validator("artifact_sha256")
    @classmethod
    def validate_digest(cls, v):
        if v is not None and not re.fullmatch(r"[0-9a-f]{64}", v):
            raise ValueError("digest must be SHA-256 hexadecimal")
        return v

    @field_validator("commit_sha")
    @classmethod
    def validate_commit(cls, v):
        if v is not None and not re.fullmatch(r"[0-9a-f]{40}", v):
            raise ValueError("commit SHA must be 40 lowercase hexadecimal characters")
        return v

def audit(db, task_id, event, payload):
    db.execute("INSERT INTO audit VALUES (?,?,?,?,?)", (str(uuid.uuid4()), task_id, event, json.dumps(payload, ensure_ascii=False), now()))

def get_existing(db, task_id):
    row = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Task not found")
    return row

def make_app():
    initialize()
    app = FastAPI(title="BaoXTra Agency Control API", version="0.4.0")
    origins = [x.strip() for x in os.getenv("AGENCY_CORS_ORIGINS", "").split(",") if x.strip()]
    if origins:
        app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=False, allow_methods=["GET","POST","PATCH"], allow_headers=["Authorization","Content-Type"])

    @app.get("/health")
    def health():
        return {"status": "healthy", "mode": "REVIEW_ONLY", "live_execution": False}

    @app.get("/api/v1/summary", dependencies=[Depends(auth)])
    def summary():
        with database() as db:
            rows = db.execute("SELECT status,count(*) AS n FROM tasks GROUP BY status").fetchall()
        counts = {x["status"]: x["n"] for x in rows}
        return {"counts": {s: counts.get(s,0) for s in STATUSES}, "verification_policy": "independent-only"}

    @app.post("/api/v1/tasks", status_code=201, dependencies=[Depends(auth)])
    def create_task(task: TaskCreate):
        task_id, created = str(uuid.uuid4()), now()
        with database() as db:
            db.execute("INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                       (task_id, task.title, task.module, task.priority, task.request, task.mode, "NOT_RUN", None, None, None, None, created, created))
            audit(db, task_id, "TASK_CREATED", {"module": task.module, "mode": task.mode})
        return {"id": task_id, "status": "NOT_RUN", "mode": task.mode, "created_at": created}

    @app.get("/api/v1/tasks", dependencies=[Depends(auth)])
    def list_tasks(module: str | None = None, priority: str | None = None, status: str | None = None, limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0)):
        filters, args = [], []
        for key, value in (("module", module), ("priority", priority), ("status", status)):
            if value is not None:
                filters.append(key + "=?")
                args.append(value)
        statement = "SELECT * FROM tasks" + (" WHERE " + " AND ".join(filters) if filters else "") + " ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?"
        with database() as db:
            result = db.execute(statement, (*args, limit, offset)).fetchall()
        return {"items": [dict(r) for r in result], "limit": limit, "offset": offset}

    @app.get("/api/v1/tasks/{task_id}", dependencies=[Depends(auth)])
    def detail(task_id: str):
        with database() as db:
            task = dict(get_existing(db, task_id))
            task["evidence"] = [dict(row) for row in db.execute("SELECT * FROM evidence WHERE task_id=? ORDER BY created_at DESC", (task_id,))]
            task["audit"] = [dict(row) for row in db.execute("SELECT * FROM audit WHERE task_id=? ORDER BY created_at DESC", (task_id,))]
        return task

    @app.patch("/api/v1/tasks/{task_id}", dependencies=[Depends(auth)])
    def update(task_id: str, patch: TaskUpdate):
        data = patch.model_dump(exclude_unset=True)
        if not data:
            raise HTTPException(400, "No changes")
        with database() as db:
            if get_existing(db, task_id)["status"] == "VERIFIED":
                raise HTTPException(409, "Locked verification record")
            db.execute("UPDATE tasks SET " + ",".join(k+"=?" for k in data) + ",updated_at=? WHERE id=?", (*data.values(),now(),task_id))
            audit(db, task_id, "TASK_UPDATED", data)
        return {"id": task_id, "verification": "NOT_VERIFIED_BY_API"}

    @app.post("/api/v1/tasks/{task_id}/evidence", status_code=201, dependencies=[Depends(auth)])
    def submit(task_id: str, ev: EvidenceCreate):
        with database() as db:
            if get_existing(db, task_id)["status"] == "VERIFIED":
                raise HTTPException(409, "Locked verification record")
            evidence_id = str(uuid.uuid4())
            db.execute("INSERT INTO evidence VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                       (evidence_id,task_id,ev.command,ev.exit_code,ev.log_url,ev.artifact_sha256,ev.commit_sha,ev.environment,None,"UNVERIFIED_SUBMISSION",now()))
            audit(db, task_id, "EVIDENCE_SUBMITTED", {"evidence_id": evidence_id, "environment": ev.environment})
        return {"id": evidence_id, "verification": "UNVERIFIED_SUBMISSION", "status_changed": False}
    return app

app = make_app()
