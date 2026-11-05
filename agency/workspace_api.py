"""Conversation, attachment intake and resumable event feed. NO LLM or media analysis."""
import asyncio
import hashlib
import json
import os
import sqlite3
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

MAX_IMAGE = 8 * 1024 * 1024
MAX_VIDEO = 25 * 1024 * 1024

def register_workspace(app, database, auth, now):
    router = APIRouter(prefix="/api/v1", dependencies=[Depends(auth)])

    def init():
        with database() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS conversations(
                id TEXT PRIMARY KEY, title TEXT NOT NULL, created_at TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS messages(
                id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL,
                role TEXT NOT NULL, body TEXT NOT NULL, created_at TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS attachments(
                id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL,
                message_id TEXT, mime TEXT NOT NULL, byte_size INTEGER NOT NULL,
                sha256 TEXT NOT NULL, storage_name TEXT NOT NULL,
                processing_status TEXT NOT NULL, created_at TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS conversation_events(
                id INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id TEXT NOT NULL,
                event_type TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL)""")
    init()

    def require(db, cid):
        if not db.execute("SELECT 1 FROM conversations WHERE id=?", (cid,)).fetchone():
            raise HTTPException(404, "Conversation not found")

    def event(db, cid, kind, payload):
        db.execute("INSERT INTO conversation_events(conversation_id,event_type,payload,created_at) VALUES(?,?,?,?)",
                   (cid, kind, json.dumps(payload, ensure_ascii=False), now()))

    class NewConversation(BaseModel):
        title: str = Field(min_length=3, max_length=120)

    class NewMessage(BaseModel):
        text: str = Field(min_length=1, max_length=8000)
        attachment_ids: list[str] = Field(default_factory=list, max_length=10)

    @router.post("/conversations", status_code=201)
    def create(request: NewConversation):
        cid = str(uuid.uuid4())
        with database() as db:
            db.execute("INSERT INTO conversations VALUES(?,?,?)", (cid, request.title, now()))
            event(db, cid, "conversation.created", {"id": cid})
        return {"id": cid, "title": request.title, "mode": "REVIEW_ONLY"}

    @router.get("/conversations")
    def list_conversations(limit: int = Query(default=50, ge=1, le=100)):
        with database() as db:
            rows = db.execute("SELECT * FROM conversations ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return {"items": [dict(r) for r in rows]}

    @router.post("/conversations/{cid}/messages", status_code=201)
    def send(cid: str, body: NewMessage):
        if len(set(body.attachment_ids)) != len(body.attachment_ids):
            raise HTTPException(422, "Duplicate attachments")
        mid = str(uuid.uuid4())
        with database() as db:
            require(db, cid)
            if body.attachment_ids:
                placeholders = ",".join("?" for _ in body.attachment_ids)
                rows = db.execute(f"SELECT id FROM attachments WHERE conversation_id=? AND message_id IS NULL AND id IN ({placeholders})",
                                  (cid, *body.attachment_ids)).fetchall()
                if len(rows) != len(body.attachment_ids):
                    raise HTTPException(422, "Attachment unknown, bound to another conversation or already used")
            db.execute("INSERT INTO messages VALUES(?,?,?,?,?)", (mid, cid, "owner", body.text, now()))
            for aid in body.attachment_ids:
                db.execute("UPDATE attachments SET message_id=? WHERE id=?", (mid, aid))
            event(db, cid, "message.created", {"id": mid, "role": "owner"})
        return {"id": mid, "role": "owner", "ai_response": "NOT_IMPLEMENTED"}

    @router.get("/conversations/{cid}/messages")
    def messages(cid: str, limit: int = Query(default=50, ge=1, le=200)):
        with database() as db:
            require(db,cid)
            rows = db.execute("SELECT * FROM messages WHERE conversation_id=? ORDER BY created_at,id LIMIT ?", (cid, limit)).fetchall()
        return {"items": [dict(r) for r in rows]}

    @router.post("/conversations/{cid}/attachments", status_code=201)
    async def upload(cid: str, file: UploadFile = File(...)):
        # Ingestion is quarantined until AV scan/media worker is added.
        mime = file.content_type or ""
        if mime not in ("image/png", "image/jpeg", "video/mp4"):
            raise HTTPException(415, "Unsupported media type")
        limit = MAX_VIDEO if mime == "video/mp4" else MAX_IMAGE
        data = await file.read(limit + 1)
        await file.close()
        if not data or len(data) > limit:
            raise HTTPException(413, "Empty or oversized media")
        valid = ((mime == "image/png" and data.startswith(b"\x89PNG\r\n\x1a\n"))
                 or (mime == "image/jpeg" and data.startswith(b"\xff\xd8\xff"))
                 or (mime == "video/mp4" and len(data) > 12 and data[4:8] == b"ftyp"))
        if not valid:
            raise HTTPException(415, "File signature mismatch")
        with database() as db:
            require(db,cid)
        aid = str(uuid.uuid4())
        path = Path(os.getenv("AGENCY_UPLOAD_PATH", "./out/quarantine"))
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        suffix = {"image/png":".png","image/jpeg":".jpg","video/mp4":".mp4"}[mime]
        stored = aid + suffix
        # Exclusive creation, opaque server-generated file names; never use client filename.
        with (path / stored).open("xb") as out:
            out.write(data)
        os.chmod(path / stored, 0o600)
        digest = hashlib.sha256(data).hexdigest()
        try:
            with database() as db:
                require(db, cid)
                db.execute("INSERT INTO attachments VALUES(?,?,?,?,?,?,?,?,?)",
                           (aid,cid,None,mime,len(data),digest,stored,"QUARANTINED_NOT_SCANNED",now()))
                event(db,cid,"attachment.received",{"id":aid,"status":"QUARANTINED_NOT_SCANNED"})
        except Exception:
            (path / stored).unlink(missing_ok=True)
            raise
        return {"id":aid,"mime":mime,"size":len(data),"sha256":digest,
                "status":"QUARANTINED_NOT_SCANNED", "analysis":"NOT_RUN"}

    @router.get("/conversations/{cid}/attachments")
    def attachments(cid: str):
        with database() as db:
            require(db,cid)
            rows = db.execute("SELECT id,mime,byte_size,sha256,processing_status,created_at,message_id FROM attachments WHERE conversation_id=? ORDER BY created_at",
                              (cid,)).fetchall()
        return {"items":[dict(r) for r in rows]}

    @router.get("/conversations/{cid}/events")
    async def events(cid: str, after: int = Query(default=0, ge=0),
                     last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
                     once: bool = False):
        cursor = after
        if last_event_id:
            try:
                cursor = max(cursor, int(last_event_id))
            except ValueError:
                raise HTTPException(422, "Invalid Last-Event-ID")
        with database() as db:
            require(db,cid)

        async def stream():
            nonlocal cursor
            # One connection may remain open 20 seconds, then client reconnects with cursor.
            for _ in range(20):
                with database() as db:
                    rows = db.execute("SELECT id,event_type,payload FROM conversation_events WHERE conversation_id=? AND id>? ORDER BY id LIMIT 100", (cid,cursor)).fetchall()
                for row in rows:
                    cursor = row["id"]
                    yield "id: " + str(cursor) + "\nevent: " + row["event_type"] + "\ndata: " + row["payload"] + "\n\n"
                if once:
                    return
                yield ": heartbeat\n\n"
                await asyncio.sleep(1)
        return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})

    app.include_router(router)
