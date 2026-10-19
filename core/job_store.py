"""Small durable store for scheduled assistant tasks.

Jobs use SQLite so a crash cannot leave a half-written JSON queue. A task that
was running when the app stopped is never replayed automatically: its last tool
may already have caused an external side effect, so it needs human review.
"""
from __future__ import annotations

import sqlite3
import sys
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


class JobStore:
    """Thread-safe, process-durable storage and state transitions for jobs."""

    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path is not None else _base_dir() / "memory" / "scheduled_jobs.db"
        self._lock = threading.RLock()
        self._initialized = False
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _connect(self):
        db = None
        try:
            db = sqlite3.connect(self.path, timeout=10)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA busy_timeout = 10000")
            db.execute("PRAGMA journal_mode = WAL")
            db.execute("PRAGMA synchronous = FULL")
            if not self._initialized:
                with self._lock:
                    if not self._initialized:
                        db.execute(
                            """CREATE TABLE IF NOT EXISTS jobs (
                                id TEXT PRIMARY KEY,
                                prompt TEXT NOT NULL,
                                due_at REAL NOT NULL,
                                status TEXT NOT NULL,
                                created_at REAL NOT NULL,
                                started_at REAL,
                                finished_at REAL,
                                attempts INTEGER NOT NULL DEFAULT 0,
                                result TEXT NOT NULL DEFAULT ''
                            )"""
                        )
                        db.execute("CREATE INDEX IF NOT EXISTS jobs_due ON jobs(status, due_at)")
                        self._initialized = True
            yield db
            db.commit()
        except Exception:
            if db is not None:
                db.rollback()
            raise
        finally:
            if db is not None:
                db.close()

    @staticmethod
    def _row(row: sqlite3.Row | None) -> dict | None:
        if row is None:
            return None
        return {
            "id": row["id"],
            "prompt": row["prompt"],
            "due_at": row["due_at"],
            "status": row["status"],
            "created_at": row["created_at"],
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
            "attempts": row["attempts"],
            "result": row["result"],
        }

    def create(self, prompt: str, due_at: float) -> dict:
        """Persist a pending one-shot job and return its record."""
        prompt = str(prompt or "").strip()
        if not prompt or len(prompt) > 2000:
            raise ValueError("Task instructions must contain 1–2000 characters.")
        due_at = float(due_at)
        if due_at <= time.time():
            raise ValueError("Scheduled time must be in the future.")
        job_id = uuid.uuid4().hex[:12]
        now = time.time()
        with self._lock, self._connect() as db:
            count = db.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('pending','running')").fetchone()[0]
            if count >= 50:
                raise ValueError("There are already 50 pending or running tasks.")
            db.execute(
                "INSERT INTO jobs (id,prompt,due_at,status,created_at) VALUES (?,?,?,'pending',?)",
                (job_id, prompt, due_at, now),
            )
            return self.get(job_id, db=db)

    def get(self, job_id: str, db: sqlite3.Connection | None = None) -> dict | None:
        """Return one job by ID, if present."""
        if db is not None:
            return self._row(db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone())
        with self._lock, self._connect() as conn:
            return self._row(conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone())

    def list(self, limit: int = 20) -> list[dict]:
        """Return recent jobs, with pending tasks ordered by due time."""
        limit = max(1, min(int(limit), 50))
        with self._lock, self._connect() as db:
            rows = db.execute(
                "SELECT * FROM jobs ORDER BY CASE WHEN status IN ('pending','running','needs_review') "
                "THEN 0 ELSE 1 END, CASE WHEN status='pending' THEN due_at ELSE created_at END, created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row(row) for row in rows]

    def claim_due(self, now: float | None = None, job_id: str | None = None) -> dict | None:
        """Atomically claim a due job; do not claim another while one runs."""
        now = time.time() if now is None else float(now)
        with self._lock, self._connect() as db:
            try:
                db.execute("BEGIN IMMEDIATE")
                if db.execute("SELECT 1 FROM jobs WHERE status='running' LIMIT 1").fetchone():
                    db.rollback()
                    return None
                if job_id is None:
                    row = db.execute(
                        "SELECT id FROM jobs WHERE status='pending' AND due_at<=? ORDER BY due_at LIMIT 1",
                        (now,),
                    ).fetchone()
                else:
                    row = db.execute(
                        "SELECT id FROM jobs WHERE status='pending' AND due_at<=? AND id=?",
                        (now, str(job_id)),
                    ).fetchone()
                if row is None:
                    db.rollback()
                    return None
                claimed_id = row["id"]
                changed = db.execute(
                    "UPDATE jobs SET status='running',started_at=?,finished_at=NULL,attempts=attempts+1 "
                    "WHERE id=? AND status='pending'",
                    (now, claimed_id),
                ).rowcount
                if changed:
                    db.commit()
                    return self.get(claimed_id, db=db)
                db.rollback()
                return None
            except Exception:
                db.rollback()
                raise

    def finish(self, job_id: str, result: str, failed: bool = False) -> bool:
        """Finish a running task as completed or failed; reject stale reports."""
        status = "failed" if failed else "completed"
        with self._lock, self._connect() as db:
            changed = db.execute(
                "UPDATE jobs SET status=?,result=?,finished_at=? WHERE id=? AND status='running'",
                (status, str(result or "")[:5000], time.time(), str(job_id)),
            ).rowcount
        return bool(changed)

    def cancel_running(self, job_id: str) -> bool:
        """Stop automatic redispatch after an interrupted in-process task."""
        with self._lock, self._connect() as db:
            changed = db.execute(
                "UPDATE jobs SET status='needs_review',finished_at=?, "
                "result='The assistant session ended before it reported completion; review before retrying.' "
                "WHERE id=? AND status='running'",
                (time.time(), str(job_id)),
            ).rowcount
        return bool(changed)

    def cancel(self, job_id: str) -> str:
        """Cancel a task only when it is not currently executing."""
        with self._lock, self._connect() as db:
            changed = db.execute(
                "UPDATE jobs SET status='cancelled',finished_at=? "
                "WHERE id=? AND status IN ('pending','failed','needs_review')",
                (time.time(), str(job_id)),
            ).rowcount
            if changed:
                return "cancelled"
            row = db.execute("SELECT status FROM jobs WHERE id=?", (str(job_id),)).fetchone()
            return "not_found" if row is None else str(row["status"])

    def retry_if_reviewed(self, job_id: str, now: float | None = None) -> str:
        """Atomically re-check the failed/review state before an approved retry."""
        now = time.time() if now is None else float(now)
        with self._lock, self._connect() as db:
            changed = db.execute(
                "UPDATE jobs SET status='pending',due_at=?,started_at=NULL,finished_at=NULL,result='' "
                "WHERE id=? AND status IN ('failed','needs_review')",
                (now, str(job_id)),
            ).rowcount
            if changed:
                return "pending"
            row = db.execute("SELECT status FROM jobs WHERE id=?", (str(job_id),)).fetchone()
            return "not_found" if row is None else str(row["status"])

    def recover_interrupted(self) -> int:
        """Move running work to needs_review; never replay a possibly-done action."""
        with self._lock, self._connect() as db:
            changed = db.execute(
                "UPDATE jobs SET status='needs_review',finished_at=?, "
                "result='Interrupted before a completion report; review before retrying.' WHERE status='running'",
                (time.time(),),
            ).rowcount
        return int(changed)


job_store = JobStore()