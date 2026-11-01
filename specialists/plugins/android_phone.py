"""Limited Android control through an explicitly authorized USB ADB connection."""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from memory.config_manager import BASE_DIR, get_plugin_config

PLUGIN = {
    "name": "android_phone",
    "description": (
        "Control a connected Android phone over USB using Android Debug Bridge. "
        "Actions: list third-party app package IDs, open an app by exact package "
        "ID, open the Contacts app for the user to choose a contact, open the dialer "
        "with a number, place a call to a number, or save a "
        "local screenshot. A saved screenshot is not automatically shown to the "
        "model. Placing a call always requires the user's separate HUD confirmation. Requires "
        "USB debugging authorization on the connected phone. Does not root the "
        "phone or access payment apps/data."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "list_apps, open_app, contacts, dial, call, or screenshot"},
            "package": {"type": "STRING", "description": "Exact Android package ID, such as com.spotify.music"},
            "phone_number": {"type": "STRING", "description": "Number to show in the dialer; the user places the call"},
        },
        "required": ["action"],
    },
}

_PACKAGE_RE = re.compile(r"^[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+$")
_NUMBER_RE = re.compile(r"^\+?[0-9][0-9 ()-]{2,24}$")
_ADB_CANDIDATES = (
    BASE_DIR / "platform-tools" / "adb.exe",
    Path(r"C:\Platform-Tools\platform-tools-latest-windows\platform-tools\adb.exe"),
)


def _adb_path() -> str | None:
    configured = get_plugin_config("android_phone").get("adb_path", "")
    if configured and Path(configured).is_file():
        return str(Path(configured))
    found = shutil.which("adb")
    if found:
        return found
    for candidate in _ADB_CANDIDATES:
        if candidate.is_file():
            return str(candidate)
    return None


def _adb(*args: str) -> str:
    adb = _adb_path()
    if not adb:
        raise RuntimeError(
            "ADB was not found. Install/extract Google's Android Platform-Tools, "
            "then add adb.exe to PATH or place it in the JARVIS platform-tools folder."
        )
    try:
        result = subprocess.run(
            [adb, "devices"], capture_output=True, text=True, timeout=10, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"Could not query ADB devices: {exc}") from exc
    devices = [line.split()[0] for line in result.stdout.splitlines()[1:] if len(line.split()) >= 2 and line.split()[1] == "device"]
    unauthorized = any("unauthorized" in line for line in result.stdout.splitlines())
    if unauthorized:
        raise RuntimeError("The phone is unauthorized. Unlock it, approve the USB debugging prompt, and retry.")
    if len(devices) != 1:
        raise RuntimeError(f"Expected exactly one authorized Android phone; found {len(devices)}. Connect only the intended phone.")
    try:
        result = subprocess.run(
            [adb, "-s", devices[0], *args], capture_output=True, text=True,
            timeout=15, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"ADB command failed: {exc}") from exc
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()[:500]
        raise RuntimeError(detail or "ADB command was unsuccessful.")
    return result.stdout.strip()


def run(parameters: dict, player=None, session_memory=None) -> str:
    action = str(parameters.get("action", "")).strip().lower()
    try:
        if action == "list_apps":
            output = _adb("shell", "pm", "list", "packages", "-3")
            packages = sorted({line.removeprefix("package:").strip() for line in output.splitlines() if line.startswith("package:")})
            if not packages:
                return "No third-party app packages were returned by Android."
            return "Installed third-party app package IDs (use the exact ID to open one):\n" + "\n".join(packages[:100])

        if action == "open_app":
            package = str(parameters.get("package", "")).strip()
            if not _PACKAGE_RE.fullmatch(package):
                return "Provide the app's exact Android package ID. Ask me to list apps to see available IDs."
            output = _adb("shell", "monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1")
            if "No activities found" in output or "monkey aborted" in output.lower():
                return f"Android has no launcher activity for {package}. It may be a service/plugin package rather than an app you can open."
            return f"Requested Android to open {package}. No app data was read or changed."

        if action == "contacts":
            output = _adb("shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", "content://com.android.contacts/contacts")
            if "Error:" in output or "unable to resolve" in output.lower():
                return "Android could not open the Contacts app."
            return "Opened Contacts on your phone. Choose the intended contact yourself; this plugin does not read or transmit your address book. After you verify their number, ask me to call that number and confirm on the JARVIS HUD."

        if action == "dial":
            number = str(parameters.get("phone_number", "")).strip()
            if not _NUMBER_RE.fullmatch(number):
                return "Please provide a valid phone number; only digits, spaces, parentheses, hyphens, and an optional leading + are allowed."
            _adb("shell", "am", "start", "-a", "android.intent.action.DIAL", "-d", f"tel:{number}")
            return f"Opened the phone dialer with {number}. Review it and tap Call yourself; JARVIS did not place a call."

        if action == "call":
            number = str(parameters.get("phone_number", "")).strip()
            if not _NUMBER_RE.fullmatch(number):
                return "Please provide a valid phone number; only digits, spaces, parentheses, hyphens, and an optional leading + are allowed."
            from core.confirm import pending_title, request
            if pending_title():
                return "There is already a confirmation waiting on the HUD. Ask the user to resolve it before requesting a call."
            return request(
                key="android_call",
                title="Place phone call",
                detail=f"Place a cellular call to {number}? Confirm to place this call on your connected Android phone.",
                run=lambda n=number: _place_call(n),
            )

        if action == "screenshot":
            adb = _adb_path()
            if not adb:
                raise RuntimeError("ADB was not found.")
            # _adb performs a fresh authorization/unique-device check first.
            _adb("shell", "echo", "connected")
            listing = subprocess.run([adb, "devices"], capture_output=True, text=True, timeout=10, check=True)
            device_ids = [line.split()[0] for line in listing.stdout.splitlines()[1:] if len(line.split()) >= 2 and line.split()[1] == "device"]
            if len(device_ids) != 1:
                raise RuntimeError("Expected exactly one authorized phone.")
            image = subprocess.run(
                [adb, "-s", device_ids[0], "exec-out", "screencap", "-p"],
                capture_output=True, timeout=15, check=True,
            ).stdout
            if not image.startswith(b"\x89PNG\r\n\x1a\n"):
                raise RuntimeError("Android did not return a valid PNG screenshot.")
            save_path = BASE_DIR / "config" / "android_screen.png"
            save_path.parent.mkdir(parents=True, exist_ok=True)
            save_path.write_bytes(image)
            return f"Saved the phone screenshot locally at {save_path}. It may contain private or payment information; JARVIS has not viewed or uploaded it. Delete the file when finished."

        return "Unknown action. Choose list_apps, open_app, contacts, dial, call, or screenshot."
    except Exception as exc:
        return f"Android phone control unavailable: {exc}"


def _place_call(number: str) -> str:
    """Place the cellular call only after the human-operated HUD gate resolves."""
    output = _adb("shell", "am", "start", "-a", "android.intent.action.CALL", "-d", f"tel:{number}")
    if "Error:" in output or "unable to resolve" in output.lower():
        raise RuntimeError("Android refused the call request; no call was placed.")
    return f"Sent the call request for {number} to Android. Android may still show its own permission or confirmation prompt."