"""Local, durable planning reviews; no operational action is executed."""
from __future__ import annotations
import json
from contextlib import contextmanager
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

class ReviewStore:
    def __init__(self, directory):
        self.directory=Path(directory)
        self.directory.mkdir(parents=True,exist_ok=True)
        self.path=self.directory/'reviews.sqlite3'
        with self.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS reviews (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                version TEXT NOT NULL, scenario TEXT NOT NULL, variant TEXT NOT NULL,
                recommendation_id TEXT NOT NULL, decision TEXT NOT NULL,
                note TEXT NOT NULL, reviewer TEXT NOT NULL, reviewed_at TEXT NOT NULL,
                checks TEXT NOT NULL)''')
            db.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path,timeout=10)
        db.row_factory=sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()
    def save_source(self, source, files=None):
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',('source',source))
            db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',('files',json.dumps(files)))
    def source(self):
        with self.connect() as db:
            values=dict(db.execute('SELECT key,value FROM settings').fetchall())
        return values.get('source','sample'),json.loads(values.get('files','null'))
    def add(self, version, scenario, variant, recommendation_id, decision, note, reviewer, checks):
        with self.connect() as db:
            cur=db.execute('INSERT INTO reviews (version,scenario,variant,recommendation_id,decision,note,reviewer,reviewed_at,checks) VALUES (?,?,?,?,?,?,?,?,?)',
                (version,scenario,variant,recommendation_id,decision,note,reviewer,datetime.now(timezone.utc).isoformat(),json.dumps(checks,sort_keys=True)))
            return cur.lastrowid
    def history(self, active_version):
        with self.connect() as db:
            records=db.execute('SELECT * FROM reviews ORDER BY sequence DESC LIMIT 500').fetchall()
        result=[]
        for record in records:
            r=dict(record); r['checks']=json.loads(r['checks']); r['stale']=r['version']!=active_version
            result.append(r)
        return result
