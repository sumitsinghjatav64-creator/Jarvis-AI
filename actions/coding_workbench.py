"""Safe staging backend for Bixy's coding workbench.

This module never asks an LLM, runs a command, or writes a file during stage().
The caller must present the diff and call apply(..., approved=True) only after
an explicit user approval.
"""
from __future__ import annotations

import difflib
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from threading import Lock

from core import confirm


class CodingWorkbench:
    def __init__(self, project_root: str | Path):
        self.project_root = Path(project_root).resolve()
        self._staged: dict[str, str] = {}
        self._backups: dict[str, str | None] = {}

    def _safe_path(self, relative_path: str) -> Path:
        candidate = (self.project_root / str(relative_path)).resolve()
        if candidate != self.project_root and self.project_root not in candidate.parents:
            raise ValueError("Path must remain inside the project root.")
        return candidate

    def stage(self, relative_path: str, content: str) -> dict:
        try:
            target = self._safe_path(relative_path)
        except ValueError as exc:
            return {"ok": False, "error": str(exc), "diff": ""}
        rel = target.relative_to(self.project_root).as_posix()
        old = target.read_text(encoding="utf-8") if target.exists() else ""
        new = str(content)
        diff = "".join(difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"a/{rel}",
            tofile=f"b/{rel}",
        ))
        self._staged[rel] = new
        return {"ok": True, "path": rel, "diff": diff, "new_file": not target.exists()}

    def check(self, command: str, timeout: int = 120) -> dict:
        """Run a test command against a temporary copy with staged files overlaid."""
        if not str(command or "").strip():
            return {"ran": False, "returncode": -1, "output": "No test command supplied."}
        with tempfile.TemporaryDirectory(prefix="bixy-workbench-") as raw:
            sandbox = Path(raw)
            shutil.copytree(self.project_root, sandbox, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns(".git", "__pycache__", ".venv", "venv", "node_modules"))
            for rel, content in self._staged.items():
                target = sandbox / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
            try:
                parts = shlex.split(command, posix=False)
                if parts and Path(parts[0]).name.lower() in {"python", "python.exe"}:
                    parts[0] = sys.executable
                result = subprocess.run(parts, cwd=sandbox, capture_output=True, text=True,
                                        encoding="utf-8", errors="replace", timeout=timeout)
                output = (result.stdout + "\n" + result.stderr).strip()
                return {"ran": True, "returncode": result.returncode, "output": output[-20000:]}
            except subprocess.TimeoutExpired as exc:
                return {"ran": True, "returncode": -2, "output": f"Test command timed out after {timeout}s: {exc}"}
            except (OSError, ValueError) as exc:
                return {"ran": True, "returncode": -1, "output": f"Could not run tests: {exc}"}

    def staged_paths(self) -> list[str]:
        return sorted(self._staged)

    def diff(self, relative_path: str) -> str:
        rel = self._safe_path(relative_path).relative_to(self.project_root).as_posix()
        if rel not in self._staged:
            return ""
        target = self.project_root / rel
        old = target.read_text(encoding="utf-8") if target.exists() else ""
        return "".join(difflib.unified_diff(
            old.splitlines(keepends=True), self._staged[rel].splitlines(keepends=True),
            fromfile=f"a/{rel}", tofile=f"b/{rel}",
        ))

    def apply(self, relative_path: str, *, approved: bool = False) -> bool:
        if not approved:
            return False
        target = self._safe_path(relative_path)
        rel = target.relative_to(self.project_root).as_posix()
        if rel not in self._staged:
            return False
        self._backups[rel] = target.read_text(encoding="utf-8") if target.exists() else None
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self._staged.pop(rel), encoding="utf-8")
        return True

    def restore(self, relative_path: str) -> bool:
        target = self._safe_path(relative_path)
        rel = target.relative_to(self.project_root).as_posix()
        if rel not in self._backups:
            return False
        previous = self._backups.pop(rel)
        if previous is None:
            target.unlink(missing_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(previous, encoding="utf-8")
        return True


_WORKBENCHES: dict[str, CodingWorkbench] = {}
_LOCK = Lock()


def _get_workbench(project_path: str) -> CodingWorkbench:
    root = str(Path(project_path).expanduser().resolve())
    with _LOCK:
        if root not in _WORKBENCHES:
            _WORKBENCHES[root] = CodingWorkbench(root)
        return _WORKBENCHES[root]


def coding_workbench(parameters: dict, player=None, **kwargs) -> str:
    params = parameters or {}
    action = str(params.get("action", "")).strip().lower()
    project_path = str(params.get("project_path", "")).strip()
    file_path = str(params.get("file_path", "")).strip()
    if not project_path or not file_path:
        return "project_path and file_path are required."
    try:
        workbench = _get_workbench(project_path)
        if action == "stage":
            result = workbench.stage(file_path, str(params.get("content", "")))
            if not result["ok"]:
                return result["error"]
            return f"Staged {result['path']} without modifying the file.\n\nDIFF:\n{result['diff'][:12000]}"
        if action == "diff":
            diff = workbench.diff(file_path)
            return diff[:12000] if diff else "No staged change found for that file."
        if action == "check":
            result = workbench.check(str(params.get("test_command", "python -m unittest discover -s .")), int(params.get("timeout", 120)))
            status = "passed" if result["ran"] and result["returncode"] == 0 else "failed"
            return f"Staged tests {status} (exit {result['returncode']}).\n\n{result['output']}"
        if action == "restore":
            return f"Restored {file_path}." if workbench.restore(file_path) else "No rollback backup found for that file."
        if action == "apply":
            diff = workbench.diff(file_path)
            if not diff:
                return "No staged change found for that file."
            return confirm.request(
                key=f"coding-workbench-{Path(project_path).name}-{file_path}",
                title=f"Apply code change: {file_path}",
                detail=f"Review this proposed change before applying it:\n\n{diff[:12000]}",
                run=lambda: f"Applied {file_path}." if workbench.apply(file_path, approved=True) else "The staged change could not be applied.",
            )
        return "Unknown action. Use stage, diff, or apply."
    except (OSError, UnicodeError, ValueError) as exc:
        return f"Coding workbench error: {exc}"


TOOL = {
    "name": "coding_workbench",
    "description": "Safely stages proposed code changes, shows unified diffs, and applies a staged change only after explicit HUD confirmation. It never writes during stage or diff.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "stage | diff | check | apply | restore"},
            "project_path": {"type": "STRING", "description": "Absolute project directory"},
            "file_path": {"type": "STRING", "description": "Relative path inside the project"},
            "content": {"type": "STRING", "description": "Complete proposed file content for stage"},
            "test_command": {"type": "STRING", "description": "Test command to run in isolated staged copy"},
            "timeout": {"type": "INTEGER", "description": "Test timeout in seconds"},
        },
        "required": ["action", "project_path", "file_path"],
    },
    "handler": coding_workbench,
}

