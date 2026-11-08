"""Tests for AV-only scanner gate. No antivirus installation needed in CI."""
import hashlib
import os
import sqlite3
import tempfile
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from agency.media_scan import scan_attachment, STATUS_CLEAN, STATUS_INFECTED, STATUS_BLOCKED, STATUS_TAMPER

class ScanTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.folder=Path(self.temp.name)
        self.db=str(self.folder/"files.db")
        self.media=self.folder/"quarantine"
        self.media.mkdir()
        with sqlite3.connect(self.db) as con:
            con.execute("""CREATE TABLE attachments(id TEXT PRIMARY KEY, conversation_id TEXT,
                mime TEXT, byte_size INTEGER, sha256 TEXT, storage_name TEXT, processing_status TEXT)""")
            con.execute("""CREATE TABLE conversation_events(conversation_id TEXT,event_type TEXT,payload TEXT,created_at TEXT)""")
        self.id=str(uuid.uuid4())
        self.data=b"\x89PNG\r\n\x1a\n"+b"fixture"
        self.path=self.media/(self.id+".png")
        self.path.write_bytes(self.data)
        self.put()

    def tearDown(self):
        self.temp.cleanup()

    def put(self):
        with sqlite3.connect(self.db) as con:
            con.execute("INSERT INTO attachments VALUES(?,?,?,?,?,?,?)",(
                self.id,"conversation-1","image/png",len(self.data),
                hashlib.sha256(self.data).hexdigest(),self.path.name,"QUARANTINED_NOT_SCANNED"))

    def get_status(self):
        with sqlite3.connect(self.db) as con:
            return con.execute("SELECT processing_status FROM attachments WHERE id=?",(self.id,)).fetchone()[0]

    def run_scan(self, code=0, runner=None):
        def stub(argv,**kwargs):
            self.assertEqual(argv[1:3],["--no-summary","--"])
            self.assertEqual(kwargs["shell"],False)
            self.assertEqual(kwargs["timeout"],45)
            return SimpleNamespace(returncode=code)
        return scan_attachment(self.id,db_path=self.db,quarantine_path=self.media,runner=runner or stub)

    def test_clean_not_vision_ready(self):
        result=self.run_scan()
        self.assertEqual(result["status"],STATUS_CLEAN)
        self.assertFalse(result["analysis_allowed"])
        self.assertEqual(self.get_status(),STATUS_CLEAN)
        with sqlite3.connect(self.db) as con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM conversation_events").fetchone()[0],1)

    def test_malware_detected(self):
        self.assertEqual(self.run_scan(code=1)["status"],STATUS_INFECTED)

    def test_scanner_error_fails_closed(self):
        self.assertEqual(self.run_scan(code=2)["status"],STATUS_BLOCKED)

    def test_missing_scanner_fails_closed(self):
        def missing(*args,**kwargs): raise FileNotFoundError("clamscan")
        self.assertEqual(self.run_scan(runner=missing)["status"],STATUS_BLOCKED)

    def test_changed_file_is_rejected_without_scan(self):
        self.path.write_bytes(self.data+b"unexpected")
        def no_call(*args,**kwargs): raise AssertionError("Should never run scanner")
        self.assertEqual(self.run_scan(runner=no_call)["status"],STATUS_TAMPER)

    def test_missing_file_is_rejected(self):
        self.path.unlink()
        self.assertEqual(self.run_scan()["status"],STATUS_TAMPER)

    def test_duplicate_scan_fails_closed(self):
        self.run_scan()
        with self.assertRaises(ValueError):
            self.run_scan()

    def test_bad_id_rejected(self):
        with self.assertRaises(ValueError):
            scan_attachment("../../etc/passwd",db_path=self.db,quarantine_path=self.media)

    def test_symlink_rejected(self):
        target=self.media/"out.png"
        target.write_bytes(self.data)
        self.path.unlink()
        self.path.symlink_to(target)
        self.assertEqual(self.run_scan()["status"],STATUS_TAMPER)

if __name__=="__main__": unittest.main()
