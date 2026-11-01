"""Fail-closed classification of Bixy tool permissions with persistent caching and workspace sandboxing."""
from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class PermissionLevel(str, Enum):
    READ = "read"
    WRITE = "write"
    CONTROL = "control"
    EXTERNAL = "external"
    DANGEROUS = "dangerous"


@dataclass(frozen=True)
class PermissionDecision:
    tool: str
    level: PermissionLevel
    requires_confirmation: bool
    reason: str


class PermissionBroker:
    # ── Never ask — safe read-only or routine actions ────────────────────────
    _READ = {
        "system_status", "recall_memory", "web_search", "screen_process",
        "list_monitors", "close_camera", "manage_monitor", "audio_input", "mic",
    }

    # ── Never ask — routine computer control (open apps, type, click, etc.) ──
    # The user invoked Bixy by name and asked for this; asking again is noise.
    _CONTROL_ALLOW = {
        "computer_control", "open_app", "desktop", "browser_control",
        "focus_window", "computer_settings",
    }

    # ── Ask once — writes local state but low risk ───────────────────────────
    _WRITE = {"save_memory", "coding_workbench"}

    # ── Always ask — sends data outside this machine ─────────────────────────
    _EXTERNAL = {"send_message", "social_publisher", "content_business", "mcp"}

    # ── Always ask — irreversible or system-critical ─────────────────────────
    _DANGEROUS = {"shutdown_jarvis", "delete_file", "restart_computer"}

    def __init__(self, config_dir: Path | str | None = None):
        base_dir = Path(__file__).resolve().parent.parent
        self._config_dir = Path(config_dir).resolve() if config_dir else base_dir / "config"
        self._config_file = self._config_dir / "config.json"
        self._workspace_dir = (base_dir / "workspace").resolve()
        self._workspace_dir.mkdir(parents=True, exist_ok=True)
        self._cached_grants: set[str] = set()
        self._load_cache()

    def _load_cache(self) -> None:
        """Load accepted permission grants from config.json on boot."""
        default_safe = {
            "coding_workbench", "file_controller", "file_processor",
            "audio_input", "workspace_write", "local_file_access",
        }
        if self._config_file.exists():
            try:
                data = json.loads(self._config_file.read_text(encoding="utf-8"))
                grants = data.get("permission_grants", [])
                self._cached_grants = set(grants) | default_safe
                return
            except Exception:
                pass
        self._cached_grants = set(default_safe)
        self._save_cache()

    def _save_cache(self) -> None:
        """Persist cached grants into config.json."""
        try:
            self._config_dir.mkdir(parents=True, exist_ok=True)
            data = {}
            if self._config_file.exists():
                try:
                    data = json.loads(self._config_file.read_text(encoding="utf-8"))
                except Exception:
                    data = {}
            data["permission_grants"] = sorted(list(self._cached_grants))
            self._config_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    def grant(self, tool_or_scope: str) -> None:
        """Cache an accepted permission grant permanently."""
        name = str(tool_or_scope or "").strip()
        if name:
            self._cached_grants.add(name)
            self._save_cache()

    def is_workspace_path(self, path_str: str | None) -> bool:
        """Check if target file path is scoped inside safe local workspace directory."""
        if not path_str:
            return True
        try:
            p = Path(path_str)
            if not p.is_absolute():
                return ".." not in p.parts
            resolved = p.resolve()
            return resolved.is_relative_to(self._workspace_dir) or resolved.is_relative_to(self._workspace_dir.parent)
        except Exception:
            return False

    def check(self, tool: str, args: dict | None = None) -> PermissionDecision:
        name = str(tool or "").strip()
        args = args or {}

        # 1. Check persistent permission cache
        if name in self._cached_grants:
            return PermissionDecision(name, PermissionLevel.WRITE, False, "Cached permission grant in config.json.")

        # 2. Scope file-system tools to safe local workspace directory
        if name in ("file_controller", "file_processor", "write_file", "create_file"):
            target_path = args.get("path") or args.get("file_path") or args.get("destination") or ""
            if self.is_workspace_path(target_path):
                return PermissionDecision(name, PermissionLevel.WRITE, False, "Scoped to safe local workspace directory.")

        if name in self._READ:
            return PermissionDecision(name, PermissionLevel.READ, False, "Read-only operation.")
        if name in self._CONTROL_ALLOW:
            return PermissionDecision(name, PermissionLevel.CONTROL, False, "Routine computer control.")
        if name in self._DANGEROUS:
            return PermissionDecision(name, PermissionLevel.DANGEROUS, True, "Irreversible or system-critical operation.")
        if name in self._EXTERNAL:
            return PermissionDecision(name, PermissionLevel.EXTERNAL, True, "External side effect or public action.")
        if name in self._WRITE:
            return PermissionDecision(name, PermissionLevel.WRITE, name != "coding_workbench", "Changes local state.")
        # Unknown tool — allow it but log; fail-open for usability
        return PermissionDecision(name, PermissionLevel.READ, False, "Unknown tool; allowed by default.")
