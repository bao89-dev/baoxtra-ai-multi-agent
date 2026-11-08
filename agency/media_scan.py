"""Trusted local AV scan adapter for quarantined uploads.

No HTTP route or AI inference. Invoked by operator in a dedicated scanner
environment with ClamAV present. Checks integrity before calling fixed binary.
A clean virus scan does NOT prove valid/safe image/video format.
"""
import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
import uuid
from pathlib import Path

STATUS_CLEAN = "AV_CLEAN_FORMAT_UNVERIFIED"
STATUS_INFECTED = "MALWARE_DETECTED"
STATUS_BLOCKED = "SCAN_FAILED_CLOSED"
STATUS_TAMPER = "INTEGRITY_MISMATCH"

def scan_attachment(attachment_id, *, db_path, quarantine_path, scanner_binary="clamscan", timeout=45, runner=subprocess.run):
    # UUID validation ensures the operator cannot supply a path.
    try:
        canonical_id = str(uuid.UUID(attachment_id))
        if canonical_id != attachment_id:
            raise ValueError("Non-canonical UUID")
    except (ValueError,TypeError,AttributeError):
        raise ValueError("Valid canonical attachment UUID required")

    conn=sqlite3.connect(db_path,timeout=10)
    conn.row_factory=sqlite3.Row
    try:
        row=conn.execute("SELECT * FROM attachments WHERE id=?", (attachment_id,)).fetchone()
        if row is None:
            raise ValueError("Attachment not found")
        if row["processing_status"] != "QUARANTINED_NOT_SCANNED":
            raise ValueError("Attachment already processed")
        # Path is derived only from trusted generated UUID+stored extension.
        suffix={"image/png":".png","image/jpeg":".jpg","video/mp4":".mp4"}.get(row["mime"])
        if not suffix or row["storage_name"] != attachment_id + suffix:
            result=STATUS_TAMPER
        else:
            folder=Path(quarantine_path).resolve(strict=True)
            path=folder / row["storage_name"]
            try:
                if path.is_symlink() or not path.is_file():
                    result=STATUS_TAMPER
                else:
                    with path.open("rb") as source:
                        data=source.read(25*1024*1024+1)
                    if len(data)!=row["byte_size"] or hashlib.sha256(data).hexdigest()!=row["sha256"]:
                        result=STATUS_TAMPER
                    else:
                        # Fixed argv, no shell or injection; scanner_binary is operator controlled.
                        try:
                            completed=runner([scanner_binary,"--no-summary","--",str(path)],
                                             shell=False, capture_output=True,text=True,timeout=timeout,
                                             env={"PATH":os.getenv("PATH","/usr/bin:/bin"),"HOME":"/nonexistent"})
                            if completed.returncode==0: result=STATUS_CLEAN
                            elif completed.returncode==1: result=STATUS_INFECTED
                            else: result=STATUS_BLOCKED
                        except (OSError,subprocess.TimeoutExpired): result=STATUS_BLOCKED
            except (OSError,ValueError):
                result=STATUS_TAMPER

        conn.execute("BEGIN IMMEDIATE")
        # Compare-and-swap: another scanner cannot overwrite a terminal decision.
        changed=conn.execute("""UPDATE attachments SET processing_status=?
          WHERE id=? AND processing_status='QUARANTINED_NOT_SCANNED'""",(result,attachment_id))
        if changed.rowcount!=1:
            conn.rollback()
            raise ValueError("Attachment state changed concurrently")
        conn.execute("""INSERT INTO conversation_events(conversation_id,event_type,payload,created_at)
          VALUES (?,?,?,datetime('now'))""",
          (row["conversation_id"],"attachment.scanned",json.dumps({
              "attachment_id":attachment_id,"status":result,"analysis_allowed":False})))
        conn.commit()
        return {"id":attachment_id,"status":result,"analysis_allowed":False}
    finally:
        conn.close()

def main():
    parser=argparse.ArgumentParser(description="Fail-closed AV scan of a quarantined attachment")
    parser.add_argument("--attachment-id",required=True)
    args=parser.parse_args()
    result=scan_attachment(args.attachment_id,
        db_path=os.getenv("AGENCY_DB_PATH","./out/control-api.sqlite3"),
        quarantine_path=os.getenv("AGENCY_UPLOAD_PATH","./out/quarantine"))
    print(json.dumps(result))
    raise SystemExit(0 if result["status"]==STATUS_CLEAN else 2)

if __name__=="__main__":
    main()
