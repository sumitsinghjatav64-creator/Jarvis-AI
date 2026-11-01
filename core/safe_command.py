"""Small allowlist for read-only commands exposed through the multi-agent worker."""
from __future__ import annotations

import os
import shlex


_WINDOWS_COMMANDS = {"tasklist", "whoami", "hostname"}
_POSIX_COMMANDS = {
    ("whoami",): ("/usr/bin/whoami",),
    ("hostname",): ("/bin/hostname",),
    ("ps", "aux"): ("/bin/ps", "aux"),
    ("uname", "-a"): ("/usr/bin/uname", "-a"),
}
_SHELL_METACHARS = set(";&|<>`$(){}\n\r\x00")


def parse_safe_command(
    command: object,
    *,
    system: str | None = None,
    system_root: str | None = None,
) -> list[str] | None:
    """Return an argv for a tiny set of read-only diagnostics, else None.

    The result always uses an absolute executable path. No shell syntax,
    interpreter, arbitrary arguments, or user-selected executable is accepted.
    """
    if not isinstance(command, str) or not command.strip() or len(command) > 256:
        return None
    if any(char in _SHELL_METACHARS for char in command):
        return None
    try:
        parts = tuple(shlex.split(command, posix=True))
    except ValueError:
        return None
    if not parts:
        return None

    os_name = (system or os.name).lower()
    if os_name in ("windows", "nt", "win32"):
        if len(parts) != 1 or parts[0].lower() not in _WINDOWS_COMMANDS:
            return None
        root = system_root or os.environ.get("SystemRoot", r"C:\Windows")
        exe = parts[0].lower() + ".exe"
        return [os.path.join(root, "System32", exe).replace("\\", "/")]

    return list(_POSIX_COMMANDS.get(parts, ())) or None
