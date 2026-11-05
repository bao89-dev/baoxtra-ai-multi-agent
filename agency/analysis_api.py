"""Analysis job intake, with strictly enforced quarantine and no model execution.

Every request persists a blocked review record. This intentionally cannot
mark scans clean or fabricate AI results; a future isolated scanner/worker
must be added with a distinct trusted identity and tests.
"""
import json
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

class AnalysisRequest(BaseModel):
    attachment_id: str = Field(min_length=36, max_length=36)
    job_type: Literal["image_review", "video_review", "ui_structure_extraction"]
    instructions: str = Field(default="", max_length=3000)

def register_analysis(app, database, auth, now):
    router = APIRouter(prefix="/api/v1", dependencies=[Depends(auth)])

    with database() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS analysis_jobs (
            id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL,
            attachment_id TEXT NOT NULL,
            job_type TEXT NOT NULL,
            instructions TEXT NOT NULL,
            status TEXT NOT NULL,
            blocker TEXT NOT NULL,
            result_summary TEXT,
            result_json TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""")

    def owned_conversation(db, conversation_id):
        if not db.execute("SELECT 1 FROM conversations WHERE id=?", (conversation_id,)).fetchone():
            raise HTTPException(404, "Conversation not found")

    def row_to_dict(row):
        return dict(row)

    @router.post("/conversations/{conversation_id}/analysis-jobs", status_code=201)
    def submit(conversation_id: str, request: AnalysisRequest):
        with database() as db:
            owned_conversation(db, conversation_id)
            attachment = db.execute(
                "SELECT id, mime, processing_status FROM attachments WHERE id=? AND conversation_id=?",
                (request.attachment_id, conversation_id)
            ).fetchone()
            if attachment is None:
                raise HTTPException(404, "Attachment not found in conversation")
            if request.job_type == "image_review" and not attachment["mime"].startswith("image/"):
                raise HTTPException(422, "Image job requires an image")
            if request.job_type == "video_review" and not attachment["mime"].startswith("video/"):
                raise HTTPException(422, "Video job requires a video")

            job_id = str(uuid.uuid4())
            # All available uploaded files are unscanned. No user-facing API
            # may bypass quarantine or assert media is trusted.
            status = "BLOCKED_SECURITY"
            blocker = "QUARANTINED_NOT_SCANNED: isolated media scanner and approved AI worker missing"
            timestamp = now()
            db.execute("""INSERT INTO analysis_jobs
                (id,conversation_id,attachment_id,job_type,instructions,status,blocker,
                 result_summary,result_json,created_at,updated_at)
                 VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (job_id, conversation_id, request.attachment_id, request.job_type,
                 request.instructions, status, blocker, None, None, timestamp, timestamp))
            db.execute("""INSERT INTO conversation_events
                (conversation_id,event_type,payload,created_at) VALUES (?,?,?,?)""",
                (conversation_id, "analysis.blocked",
                 json.dumps({"job_id": job_id, "status": status}), timestamp))
        return {"id": job_id, "status": status, "blocker": blocker,
                "result_summary": None, "model_executed": False}

    @router.get("/conversations/{conversation_id}/analysis-jobs")
    def list_jobs(conversation_id: str, limit: int = Query(default=50, ge=1, le=100)):
        with database() as db:
            owned_conversation(db, conversation_id)
            rows = db.execute("""SELECT * FROM analysis_jobs
                WHERE conversation_id=? ORDER BY created_at DESC,id DESC LIMIT ?""",
                (conversation_id, limit)).fetchall()
        return {"items": [row_to_dict(row) for row in rows]}

    @router.get("/analysis-jobs/{job_id}")
    def get_job(job_id: str):
        with database() as db:
            row = db.execute("SELECT * FROM analysis_jobs WHERE id=?", (job_id,)).fetchone()
            if row is None:
                raise HTTPException(404, "Analysis job not found")
            return row_to_dict(row)

    app.include_router(router)
