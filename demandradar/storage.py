from __future__ import annotations
"""Auditable SQLite storage; deduplicates public posts without losing review state."""
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3
from typing import Iterator
from .sources import Candidate
from .scoring import score_opportunity


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, path: str):
        self.path = path
        Path(path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA busy_timeout=5000")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def init_db(self):
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS opportunities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    url TEXT NOT NULL UNIQUE,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    published_at TEXT NOT NULL,
                    project_context TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'new',
                    score INTEGER NOT NULL,
                    category TEXT NOT NULL,
                    budget_evidence TEXT,
                    reasons_json TEXT NOT NULL,
                    note TEXT NOT NULL DEFAULT '',
                    discovered_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(source,source_id)
                );
                CREATE INDEX IF NOT EXISTS opportunities_filter
                    ON opportunities(status,score DESC,discovered_at DESC);
                CREATE TABLE IF NOT EXISTS activity (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    opportunity_id INTEGER REFERENCES opportunities(id),
                    event TEXT NOT NULL,
                    detail TEXT NOT NULL DEFAULT '',
                    occurred_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS scans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL, search_key TEXT NOT NULL,
                    fetched_count INTEGER NOT NULL, new_count INTEGER NOT NULL,
                    outcome TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '',
                    occurred_at TEXT NOT NULL
                );
            """)

    @staticmethod
    def _row(r: sqlite3.Row) -> dict:
        x = dict(r)
        if "reasons_json" in x:
            x["reasons"] = json.loads(x.pop("reasons_json"))
        return x

    def ingest(self, candidates: list[Candidate]) -> dict:
        seen = len(candidates)
        inserted = 0
        with self.connect() as db:
            for c in candidates:
                if not c.title.strip():
                    continue
                result = score_opportunity(c.title, c.description, c.published_at)
                stamp = utcnow()
                cur = db.execute("""
                    INSERT OR IGNORE INTO opportunities (
                        source,source_id,url,title,description,published_at,project_context,
                        score,category,budget_evidence,reasons_json,discovered_at,updated_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (c.source,c.source_id,c.url,c.title,c.description,c.published_at,
                      c.project_context,result.value,result.category,result.budget_evidence,
                      json.dumps(result.reasons),stamp,stamp))
                if cur.rowcount:
                    inserted += 1
                    db.execute("INSERT INTO activity(opportunity_id,event,detail,occurred_at) VALUES (?,?,?,?)",
                               (cur.lastrowid,"discovered",c.source,stamp))
            return {"fetched": seen,"new": inserted,"duplicates": max(0,seen-inserted)}

    def list(self, status: str = "all", min_score: int = 0, limit: int = 100,
             query: str = "") -> list[dict]:
        sql = "SELECT * FROM opportunities WHERE score>=?"
        params: list = [min_score]
        if status != "all":
            sql += " AND status=?"
            params.append(status)
        if query:
            sql += " AND (title LIKE ? OR description LIKE ? OR category LIKE ?)"
            q = "%" + query[:100].replace("%", "\\%").replace("_", "\\_") + "%"
            # SQLite LIKE escaping supplied via explicit escape clause on each predicate.
            sql = sql.replace("title LIKE ? OR description LIKE ? OR category LIKE ?",
                              "title LIKE ? ESCAPE '\\' OR description LIKE ? ESCAPE '\\' OR category LIKE ? ESCAPE '\\'")
            params.extend([q,q,q])
        sql += " ORDER BY score DESC, discovered_at DESC, id DESC LIMIT ?"
        params.append(max(1,min(limit,250)))
        with self.connect() as db:
            return [self._row(r) for r in db.execute(sql,params).fetchall()]

    def get(self, record_id: int) -> dict | None:
        with self.connect() as db:
            r = db.execute("SELECT * FROM opportunities WHERE id=?",(record_id,)).fetchone()
            return self._row(r) if r else None

    def update_status(self, record_id: int, status: str, note: str) -> dict | None:
        stamp = utcnow()
        with self.connect() as db:
            cur = db.execute("UPDATE opportunities SET status=?,note=?,updated_at=? WHERE id=?",
                             (status,note,stamp,record_id))
            if not cur.rowcount:
                return None
            db.execute("INSERT INTO activity(opportunity_id,event,detail,occurred_at) VALUES (?,?,?,?)",
                       (record_id,"status:"+status,note[:250],stamp))
        return self.get(record_id)

    def log_scan(self, source: str, search_key: str, fetched: int, new: int,
                 outcome: str, detail: str = "") -> None:
        with self.connect() as db:
            db.execute("INSERT INTO scans(source,search_key,fetched_count,new_count,outcome,detail,occurred_at) VALUES (?,?,?,?,?,?,?)",
                       (source,search_key,fetched,new,outcome,detail[:500],utcnow()))

    def scans(self, limit: int = 12) -> list[dict]:
        with self.connect() as db:
            return [dict(r) for r in db.execute("SELECT * FROM scans ORDER BY id DESC LIMIT ?",(limit,))]

    def summary(self) -> dict:
        with self.connect() as db:
            total = db.execute("SELECT COUNT(*) AS n FROM opportunities").fetchone()["n"]
            high = db.execute("SELECT COUNT(*) AS n FROM opportunities WHERE score>=65").fetchone()["n"]
            shortlisted = db.execute("SELECT COUNT(*) AS n FROM opportunities WHERE status='shortlisted'").fetchone()["n"]
            contacted = db.execute("SELECT COUNT(*) AS n FROM opportunities WHERE status IN ('contacted','replied')").fetchone()["n"]
            won = db.execute("SELECT COUNT(*) AS n FROM opportunities WHERE status='won'").fetchone()["n"]
            categories = [dict(r) for r in db.execute("SELECT category,COUNT(*) AS count FROM opportunities GROUP BY category ORDER BY count DESC")]
            sources = [dict(r) for r in db.execute("SELECT source,COUNT(*) AS count FROM opportunities GROUP BY source ORDER BY count DESC")]
            return {"total":total,"high_priority":high,"shortlisted":shortlisted,"contacted":contacted,
                    "won":won,"categories":categories,"sources":sources}
