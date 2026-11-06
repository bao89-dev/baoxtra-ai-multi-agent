"""Versioned design proposals and owner decisions. No agent execution.

A human-issued decision is bound to the exact version and SHA-256 of a
canonicalized proposal. Every revision supersedes earlier approvals.
Owner decision requires separate approval credential.
"""
import hashlib
import hmac
import json
import os
import re
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field, model_validator


class PlanTask(BaseModel):
    id: str = Field(pattern=r"^[A-Z][A-Z0-9_-]{1,23}$")
    title: str = Field(min_length=3, max_length=160)
    depends_on: list[str] = Field(default_factory=list, max_length=20)


class ProposalContent(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    summary: str = Field(min_length=10, max_length=6000)
    diagram: str = Field(min_length=3, max_length=12000)
    tasks: list[PlanTask] = Field(min_length=1, max_length=60)

    @model_validator(mode="after")
    def validate_task_dag(self):
        refs = {task.id for task in self.tasks}
        if len(refs) != len(self.tasks):
            raise ValueError("Duplicate task IDs")
        graph = {t.id: t.depends_on for t in self.tasks}
        for task in self.tasks:
            if len(set(task.depends_on)) != len(task.depends_on):
                raise ValueError("Duplicate dependency")
            if any(dep not in refs for dep in task.depends_on):
                raise ValueError("Unknown dependency")
        visited, active = set(), set()
        def walk(node):
            if node in active:
                raise ValueError("Cycle detected in task DAG")
            if node in visited:
                return
            active.add(node)
            for dep in graph[node]:
                walk(dep)
            active.remove(node)
            visited.add(node)
        for node in refs:
            walk(node)
        return self


class ProposalCreate(ProposalContent):
    conversation_id: str


class ProposalRevision(ProposalContent):
    expected_version: int = Field(ge=1)


class OwnerDecision(BaseModel):
    expected_version: int = Field(ge=1)
    expected_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    action: Literal["APPROVE", "REQUEST_CHANGES", "REJECT"]
    reason: str = Field(min_length=3, max_length=2000)


def canonical(content: ProposalContent):
    return json.dumps(content.model_dump(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(content):
    return hashlib.sha256(canonical(content).encode("utf8")).hexdigest()


def register_proposals(app, database, auth, now):
    router = APIRouter(prefix="/api/v1", dependencies=[Depends(auth)])
    with database() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS design_proposals(
          id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL, current_version INTEGER NOT NULL,
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
        db.execute("""CREATE TABLE IF NOT EXISTS design_proposal_versions(
          proposal_id TEXT NOT NULL, version INTEGER NOT NULL, payload TEXT NOT NULL,
          sha256 TEXT NOT NULL, created_at TEXT NOT NULL,
          PRIMARY KEY (proposal_id, version))""")
        db.execute("""CREATE TABLE IF NOT EXISTS design_proposal_decisions(
          id TEXT PRIMARY KEY, proposal_id TEXT NOT NULL, version INTEGER NOT NULL,
          sha256 TEXT NOT NULL, action TEXT NOT NULL, reason TEXT NOT NULL,
          actor TEXT NOT NULL, created_at TEXT NOT NULL,
          UNIQUE (proposal_id, version))""")

    def get_proposal(db, pid):
        item = db.execute("SELECT * FROM design_proposals WHERE id=?", (pid,)).fetchone()
        if item is None:
            raise HTTPException(404, "Proposal not found")
        return item

    def latest(db, proposal):
        version = db.execute(
            "SELECT * FROM design_proposal_versions WHERE proposal_id=? AND version=?",
            (proposal["id"], proposal["current_version"])
        ).fetchone()
        decision = db.execute(
            "SELECT action,reason,actor,created_at FROM design_proposal_decisions WHERE proposal_id=? AND version=?",
            (proposal["id"], proposal["current_version"])
        ).fetchone()
        return {"id": proposal["id"], "conversation_id": proposal["conversation_id"],
                "version": proposal["current_version"], "sha256": version["sha256"],
                "content": json.loads(version["payload"]),
                "status": decision["action"] if decision else "DRAFT",
                "decision": dict(decision) if decision else None,
                "execution": "NOT_AUTHORIZED_BY_THIS_SERVICE"}

    @router.post("/proposals", status_code=201)
    def create(request: ProposalCreate):
        pid = str(uuid.uuid4())
        data = ProposalContent(**request.model_dump(exclude={"conversation_id"}))
        content = canonical(data)
        checksum = digest(data)
        stamp = now()
        with database() as db:
            if not db.execute("SELECT 1 FROM conversations WHERE id=?", (request.conversation_id,)).fetchone():
                raise HTTPException(404, "Conversation not found")
            db.execute("INSERT INTO design_proposals VALUES (?,?,?,?,?)",
                       (pid, request.conversation_id, 1, stamp, stamp))
            db.execute("INSERT INTO design_proposal_versions VALUES (?,?,?,?,?)",
                       (pid,1,content,checksum,stamp))
            db.execute("""INSERT INTO conversation_events(conversation_id,event_type,payload,created_at)
              VALUES (?,?,?,?)""",
              (request.conversation_id,"proposal.created",json.dumps({"id":pid,"version":1}),stamp))
        return {"id":pid, "version":1, "sha256":checksum,"status":"DRAFT","execution":"NOT_AUTHORIZED"}

    @router.get("/conversations/{cid}/proposals")
    def list_for_conversation(cid: str, limit: int = Query(default=30,ge=1,le=100)):
        with database() as db:
            if not db.execute("SELECT 1 FROM conversations WHERE id=?", (cid,)).fetchone():
                raise HTTPException(404,"Conversation not found")
            rows = db.execute("SELECT * FROM design_proposals WHERE conversation_id=? ORDER BY updated_at DESC LIMIT ?",
                              (cid,limit)).fetchall()
            return {"items":[latest(db,p) for p in rows]}

    @router.get("/proposals/{pid}")
    def read(pid: str):
        with database() as db:
            return latest(db, get_proposal(db,pid))

    @router.post("/proposals/{pid}/revisions", status_code=201)
    def revise(pid: str, request: ProposalRevision):
        data = ProposalContent(**request.model_dump(exclude={"expected_version"}))
        content, checksum = canonical(data),digest(data)
        stamp=now()
        with database() as db:
            proposal = get_proposal(db,pid)
            if proposal["current_version"] != request.expected_version:
                raise HTTPException(409,"Stale proposal version")
            new_version = request.expected_version+1
            db.execute("INSERT INTO design_proposal_versions VALUES (?,?,?,?,?)",
                       (pid,new_version,content,checksum,stamp))
            db.execute("UPDATE design_proposals SET current_version=?,updated_at=? WHERE id=?",
                       (new_version,stamp,pid))
            db.execute("INSERT INTO conversation_events(conversation_id,event_type,payload,created_at) VALUES (?,?,?,?)",
                       (proposal["conversation_id"],"proposal.revised",
                        json.dumps({"id":pid,"version":new_version}),stamp))
            return {"id":pid,"version":new_version,"sha256":checksum,"status":"DRAFT",
                    "prior_approvals_not_effective":True}

    @router.post("/proposals/{pid}/decision")
    def decision(pid: str, request: OwnerDecision, x_owner_approval_key: str | None = Header(default=None)):
        token=os.getenv("AGENCY_APPROVAL_TOKEN","")
        backend_token=os.getenv("AGENCY_API_TOKEN","")
        if len(token)<32 or hmac.compare_digest(token,backend_token):
            raise HTTPException(503,"Owner approval credential not configured independently")
        if not x_owner_approval_key or not hmac.compare_digest(x_owner_approval_key,token):
            raise HTTPException(403,"Owner approval key required")
        stamp=now()
        with database() as db:
            proposal = get_proposal(db,pid)
            if proposal["current_version"] != request.expected_version:
                raise HTTPException(409,"Stale proposal version")
            snapshot = latest(db,proposal)
            if not hmac.compare_digest(snapshot["sha256"],request.expected_sha256):
                raise HTTPException(409,"Proposal content hash mismatch")
            if snapshot["decision"] is not None:
                raise HTTPException(409,"Version already decided")
            db.execute("""INSERT INTO design_proposal_decisions
             (id,proposal_id,version,sha256,action,reason,actor,created_at)
             VALUES (?,?,?,?,?,?,?,?)""",
             (str(uuid.uuid4()),pid,request.expected_version,request.expected_sha256,
              request.action,request.reason,"owner-session",stamp))
            db.execute("INSERT INTO conversation_events(conversation_id,event_type,payload,created_at) VALUES (?,?,?,?)",
                       (proposal["conversation_id"],"proposal.decided",
                        json.dumps({"id":pid,"version":request.expected_version,"action":request.action}),stamp))
        return {"id":pid,"version":request.expected_version,"status":request.action,
                "sha256":request.expected_sha256,
                "execution":"NOT_AUTHORIZED_BY_THIS_SERVICE"}

    app.include_router(router)
