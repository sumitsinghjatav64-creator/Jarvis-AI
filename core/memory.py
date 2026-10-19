import sqlite3
import json
from typing import Any, Dict, List, Optional
from pathlib import Path
from core.models import SubTask, TaskPlan, ExecutionResult
from config.settings import settings

class MemoryWorker:
    """
    Persistent task history and lightweight session state worker using SQLite.
    Schema includes vector/embedding-ready placeholder column for semantic retrieval.
    """
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or settings.DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS task_history (
                    task_id TEXT PRIMARY KEY,
                    plan_id TEXT,
                    description TEXT,
                    worker_type TEXT,
                    input_data TEXT,
                    status TEXT,
                    result TEXT,
                    embedding BLOB,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS session_state (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def record_subtask(self, plan_id: str, task: SubTask):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO task_history 
                (task_id, plan_id, description, worker_type, input_data, status, result)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                task.task_id,
                plan_id,
                task.description,
                task.worker_type.value,
                json.dumps(task.input_data),
                task.status.value,
                task.result.model_dump_json() if task.result else None
            ))
            conn.commit()

    def get_past_subtasks(self, limit: int = 10) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT task_id, plan_id, description, worker_type, status, result, timestamp
                FROM task_history ORDER BY timestamp DESC LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            return [
                {
                    "task_id": r[0],
                    "plan_id": r[1],
                    "description": r[2],
                    "worker_type": r[3],
                    "status": r[4],
                    "result": json.loads(r[5]) if r[5] else None,
                    "timestamp": r[6]
                }
                for r in rows
            ]

    def set_state(self, key: str, value: Any):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO session_state (key, value)
                VALUES (?, ?)
            """, (key, json.dumps(value)))
            conn.commit()

    def get_state(self, key: str) -> Optional[Any]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM session_state WHERE key = ?", (key,))
            row = cursor.fetchone()
            return json.loads(row[0]) if row else None
