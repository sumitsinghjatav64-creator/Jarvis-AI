"""Persistent, UI-facing to-do tasks shared by the desktop and web UI."""
from __future__ import annotations

import sqlite3
import sys
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


class TodoStore:
    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path is not None else _base_dir() / "memory" / "todo_tasks.db"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA busy_timeout = 10000")
            db.execute(
                """CREATE TABLE IF NOT EXISTS todo_tasks (
                    id TEXT PRIMARY KEY,
                    text TEXT NOT NULL,
                    completed INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL
                )"""
            )
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _task(row: sqlite3.Row) -> dict:
        return {
            "id": row["id"],
            "text": row["text"],
            "completed": bool(row["completed"]),
            "created_at": row["created_at"],
        }

    def list_tasks(self, limit: int = 100) -> list[dict]:
        limit = max(1, min(int(limit), 200))
        with self._connect() as db:
            rows = db.execute(
                "SELECT id,text,completed,created_at FROM todo_tasks "
                "ORDER BY completed ASC, created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._task(row) for row in rows]

    def add_task(self, text: str) -> dict:
        text = str(text or "").strip()
        if not text or len(text) > 500:
            raise ValueError("Task text must contain 1–500 characters.")
        task = {"id": uuid.uuid4().hex[:16], "text": text, "completed": False, "created_at": time.time()}
        with self._connect() as db:
            db.execute(
                "INSERT INTO todo_tasks (id,text,completed,created_at) VALUES (?,?,0,?)",
                (task["id"], task["text"], task["created_at"]),
            )
        return task

    def set_completed(self, task_id: str, completed: bool) -> bool:
        if not isinstance(completed, bool):
            return False
        with self._connect() as db:
            changed = db.execute(
                "UPDATE todo_tasks SET completed=? WHERE id=?",
                (int(completed), str(task_id)),
            ).rowcount
        return bool(changed)

    def delete_task(self, task_id: str) -> bool:
        with self._connect() as db:
            changed = db.execute("DELETE FROM todo_tasks WHERE id=?", (str(task_id),)).rowcount
        return bool(changed)


# Shared singleton used by both UI surfaces.
todo_store = TodoStore()
