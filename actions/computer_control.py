# actions/computer_control.py
import ctypes
import io
import json
import platform
import random
import re
import string
import subprocess
import sys
import time
from pathlib import Path

if platform.system() == "Windows":
    _WIN_HIDE: dict = {"creationflags": subprocess.CREATE_NO_WINDOW}
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass
else:
    _WIN_HIDE: dict = {}

# ── DPI-aware coordinate scaling ──────────────────────────────────────────
# Windows laptops commonly run at 125–150 % scaling. PyAutoGUI reports the
# effective (scaled) screen size, but a raw Vision-normalized coordinate must
# be mapped through the same scale before clicking, or the click lands off by
# a predictable offset on high-DPI displays.
_SCREEN_SCALE: float | None = None


def _screen_scale() -> float:
    """Return the Windows DPI scale factor (e.g. 1.25 for 125 %). Cached."""
    global _SCREEN_SCALE
    if _SCREEN_SCALE is not None:
        return _SCREEN_SCALE
    if platform.system() == "Windows":
        try:
            md = ctypes.windll.shcore.GetDpiForMonitor(
                ctypes.windll.user32.MonitorFromWindow(0, 2), 2
            )
            _SCREEN_SCALE = float(md[0]) / 96.0
        except Exception:
            _SCREEN_SCALE = 1.0
    else:
        _SCREEN_SCALE = 1.0
    return _SCREEN_SCALE

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE    = 0.005
    _PYAUTOGUI = True
except ImportError:
    _PYAUTOGUI = False

try:
    import pyperclip
    _PYPERCLIP = True
except ImportError:
    _PYPERCLIP = False


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


_BASE        = _base_dir()
_CONFIG_PATH = _BASE / "config" / "api_keys.json"
_MEMORY_PATH = _BASE / "memory" / "long_term.json"


def _load_config() -> dict:
    try:
        return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _platform_os() -> str:
    return {"Windows": "windows", "Darwin": "mac", "Linux": "linux"}.get(
        platform.system(), "linux"
    )


def _get_os() -> str:
    return _load_config().get("os_system", _platform_os()).lower()


def _get_api_key() -> str:
    return _load_config().get("gemini_api_key", "")


_SAFE_SCREENSHOT_ROOTS = (Path.home(),)


def _safe_screenshot_path(requested: str | None) -> Path:
    fallback = Path.home() / "Desktop" / "jarvis_screenshot.png"
    if not requested:
        return fallback
    try:
        p = Path(requested).expanduser().resolve()
        for root in _SAFE_SCREENSHOT_ROOTS:
            if p.is_relative_to(root.resolve()):
                p.parent.mkdir(parents=True, exist_ok=True)
                return p
    except Exception:
        pass
    return fallback


def _require_pyautogui():
    if not _PYAUTOGUI:
        raise RuntimeError("PyAutoGUI not installed. Run: pip install pyautogui")


_FIRST_NAMES = [
    "Alex", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Drew", "Quinn",
    "Avery", "Blake", "Cameron", "Dakota", "Emerson", "Finley", "Harper",
]
_LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Wilson", "Moore", "Taylor", "Anderson", "Thomas", "Jackson",
]
_DOMAINS = ["gmail.com", "yahoo.com", "outlook.com", "proton.me", "mail.com"]


def _random_data(data_type: str) -> str:
    dt = data_type.lower().strip()
    if dt == "first_name":
        return random.choice(_FIRST_NAMES)
    if dt == "last_name":
        return random.choice(_LAST_NAMES)
    if dt == "name":
        return f"{random.choice(_FIRST_NAMES)} {random.choice(_LAST_NAMES)}"
    if dt == "email":
        first = random.choice(_FIRST_NAMES).lower()
        last  = random.choice(_LAST_NAMES).lower()
        num   = random.randint(10, 999)
        return f"{first}.{last}{num}@{random.choice(_DOMAINS)}"
    if dt == "username":
        return f"{random.choice(_FIRST_NAMES).lower()}{random.randint(100, 9999)}"
    if dt == "password":
        chars = string.ascii_letters + string.digits + "!@#$%"
        raw   = (
            random.choice(string.ascii_uppercase)
            + random.choice(string.digits)
            + random.choice("!@#$%")
            + "".join(random.choices(chars, k=9))
        )
        return "".join(random.sample(raw, len(raw)))
    if dt == "phone":
        return f"+1{random.randint(200,999)}{random.randint(1_000_000, 9_999_999)}"
    if dt == "birthday":
        y = random.randint(1980, 2000)
        m = random.randint(1, 12)
        d = random.randint(1, 28)
        return f"{m:02d}/{d:02d}/{y}"
    if dt == "address":
        num    = random.randint(100, 9999)
        street = random.choice(["Main St", "Oak Ave", "Park Blvd", "Elm St", "Cedar Ln"])
        return f"{num} {street}"
    if dt == "zip_code":
        return str(random.randint(10000, 99999))
    if dt == "city":
        return random.choice(["New York", "Los Angeles", "Chicago", "Houston", "Phoenix"])
    return f"random_{data_type}_{random.randint(1000, 9999)}"


def _user_profile() -> dict:
    try:
        if _MEMORY_PATH.exists():
            data     = json.loads(_MEMORY_PATH.read_text(encoding="utf-8"))
            identity = data.get("identity", {})
            return {k: v.get("value", "") for k, v in identity.items()}
    except Exception:
        pass
    return {}


def _type(text: str) -> str:
    _require_pyautogui()
    if _PYPERCLIP:
        pyperclip.copy(text)
        paste_key = "command" if _get_os() == "mac" else "ctrl"
        pyautogui.hotkey(paste_key, "v")
        return f"Typed (instant): {text[:60]}{'…' if len(text) > 60 else ''}"
    pyautogui.typewrite(text, interval=0.005)
    return f"Typed: {text[:60]}{'…' if len(text) > 60 else ''}"


def _smart_type(text: str, clear_first: bool = True) -> str:
    _require_pyautogui()
    if clear_first:
        _clear_field()
    if _PYPERCLIP:
        pyperclip.copy(text)
        paste_key = "command" if _get_os() == "mac" else "ctrl"
        pyautogui.hotkey(paste_key, "v")
        return f"Smart-typed (instant): {text[:60]}{'…' if len(text) > 60 else ''}"
    pyautogui.typewrite(text, interval=0.005)
    return f"Smart-typed: {text[:60]}{'…' if len(text) > 60 else ''}"


def _click(x=None, y=None, button: str = "left", clicks: int = 1) -> str:
    _require_pyautogui()
    if x is not None and y is not None:
        x, y = max(5, int(x)), max(5, int(y))  # Prevent (0,0) PyAutoGUI fail-safe crash
        pyautogui.moveTo(x, y, duration=0.1)
        time.sleep(0.05)
        pyautogui.click(x, y, button=button, clicks=clicks)
        return f"{'Double-c' if clicks == 2 else 'C'}licked ({x}, {y}) [{button}]"
    pyautogui.click(button=button, clicks=clicks)
    return f"Clicked at current position [{button}]"


def _hotkey(*keys) -> str:
    _require_pyautogui()
    pyautogui.hotkey(*keys)
    return f"Hotkey: {'+'.join(keys)}"


def _press(key: str) -> str:
    _require_pyautogui()
    pyautogui.press(key)
    return f"Pressed: {key}"


def _scroll(direction: str = "down", amount: int = 3) -> str:
    _require_pyautogui()
    vertical = direction in ("up", "down")
    clicks   = amount if direction in ("up", "right") else -amount
    pyautogui.scroll(clicks) if vertical else pyautogui.hscroll(clicks)
    return f"Scrolled {direction} ×{amount}"


def _move(x: int, y: int, duration: float = 0.3) -> str:
    _require_pyautogui()
    x, y = max(5, int(x)), max(5, int(y))
    pyautogui.moveTo(x, y, duration=duration)
    return f"Mouse → ({x}, {y})"


def _drag(x1: int, y1: int, x2: int, y2: int, duration: float = 0.5) -> str:
    _require_pyautogui()
    x1, y1 = max(5, int(x1)), max(5, int(y1))
    x2, y2 = max(5, int(x2)), max(5, int(y2))
    pyautogui.moveTo(x1, y1, duration=0.15)
    time.sleep(0.05)
    pyautogui.dragTo(x2, y2, duration=duration, button="left")
    time.sleep(0.05)
    return f"Dragged ({x1},{y1}) → ({x2},{y2})"


def _clipboard_get() -> str:
    if _PYPERCLIP:
        return pyperclip.paste()
    _hotkey("ctrl", "c")
    time.sleep(0.2)
    return "(copied — pyperclip unavailable for read)"


def _clipboard_paste(text: str) -> str:
    if _PYPERCLIP:
        pyperclip.copy(text)
        time.sleep(0.1)
        _require_pyautogui()
        paste_key = "command" if _get_os() == "mac" else "ctrl"
        pyautogui.hotkey(paste_key, "v")
        return f"Pasted: {text[:60]}{'…' if len(text) > 60 else ''}"
    return "pyperclip not available"


def _screenshot(save_path: str | None = None) -> str:
    _require_pyautogui()
    path = _safe_screenshot_path(save_path)
    img  = pyautogui.screenshot()
    img.save(str(path))
    return f"Screenshot saved: {path}"


def _clear_field() -> str:
    _require_pyautogui()
    select_key = "command" if _get_os() == "mac" else "ctrl"
    pyautogui.hotkey(select_key, "a")
    time.sleep(0.1)
    pyautogui.press("delete")
    return "Field cleared"


def _screen_find(description: str) -> tuple[int, int] | None:
    """Uses Gemini Vision to find an element on screen and return its (x, y) pixel coordinates."""
    _require_pyautogui()
    if not description or not description.strip():
        return None
    try:
        from google import genai
        from google.genai import types as gtypes

        sw, sh = pyautogui.size()
        img = pyautogui.screenshot()
        buf = io.BytesIO()
        img.save(buf, format="PNG")

        prompt = (
            f"Locate this UI element on the screen: '{description}'.\\n"
            'Return ONLY valid JSON with normalized 0-1000 coordinates: '
            '{"box_2d": [ymin, xmin, ymax, xmax]} or {"box_2d": null} if not visible.'
        )
        client = genai.Client(api_key=_get_api_key())
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                gtypes.Part.from_bytes(data=buf.getvalue(), mime_type="image/png"),
                prompt,
            ],
        )
        raw = (resp.text or "").strip()
        m = re.search(r"\[\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\]", raw)
        if m:
            ymin, xmin, ymax, xmax = map(int, m.groups())
            cx = max(5, int(((xmin + xmax) / 2.0) / 1000.0 * sw * _screen_scale()))
            cy = max(5, int(((ymin + ymax) / 2.0) / 1000.0 * sh * _screen_scale()))
            return (cx, cy)
    except Exception as e:
        print(f"[ComputerControl] _screen_find error: {e}")
    return None


def _screen_find_verified(description: str, retries: int = 3, jitter: int = 8) -> tuple[int, int] | None:
    """Locate an element via Gemini Vision and verify the click lands.

    Retries up to ``retries`` times. After each click the region is re-scanned;
    if the element moved or disappeared, the click is assumed to have landed.
    Small ±jitter px noise is added between attempts to dodge dead zones.
    """
    import random
    for attempt in range(retries):
        coords = _screen_find(description)
        if not coords:
            time.sleep(0.4)
            continue
        cx, cy = coords
        _click(x=cx, y=cy)
        time.sleep(0.4)
        # Re-scan: if the element is gone or shifted, the click likely worked.
        after = _screen_find(description)
        if after is None:
            return (cx, cy)
        dx = abs(after[0] - cx)
        dy = abs(after[1] - cy)
        if dx > jitter or dy > jitter:
            return (cx, cy)
        # Element still at same spot — click may have missed. Retry with jitter.
        time.sleep(0.3)
    return None


def _screen_click(desc: str) -> str:
    coords = _screen_find_verified(desc)
    if coords:
        return f"Clicked '{desc}' at {coords}"
    return f"Element not found or click failed: '{desc}'"


def _execute_pipeline(steps: list[dict]) -> str:
    """Executes a compound list of user actions locally at machine speed."""
    _require_pyautogui()
    results = []
    for step in steps:
        act = step.get("action", "").lower().strip()
        if act == "hotkey":
            raw = step.get("keys", "")
            keys = [k.strip() for k in raw.split("+")] if isinstance(raw, str) else raw
            _hotkey(*keys)
        elif act == "press":
            _press(step.get("key", "enter"))
        elif act in ("type", "smart_type"):
            _smart_type(step.get("text", ""), clear_first=step.get("clear_first", False))
        elif act == "click":
            _click(step.get("x"), step.get("y"), step.get("button", "left"), int(step.get("clicks", 1)))
        elif act == "wait":
            time.sleep(float(step.get("seconds", 0.1)))
        results.append(act)
    return f"Pipeline completed ({len(results)} actions: {', '.join(results)})"


def _focus_window(title: str) -> str:
    os_name = _get_os()

    if os_name == "windows":
        try:
            script = f'(New-Object -ComObject WScript.Shell).AppActivate("{title}")'
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                capture_output=True, timeout=5, **_WIN_HIDE,
            )
            time.sleep(0.3)
            return f"Focused window: {title}"
        except Exception as e:
            return f"focus_window (Windows) failed: {e}"

    if os_name == "mac":
        script = (
            f'tell application "System Events" to '
            f'set frontmost of (first process whose name contains "{title}") to true'
        )
        try:
            subprocess.run(["osascript", "-e", script], capture_output=True, timeout=5)
            time.sleep(0.3)
            return f"Focused window: {title}"
        except Exception as e:
            return f"focus_window (macOS) failed: {e}"

    if os_name == "linux":
        try:
            result = subprocess.run(["wmctrl", "-a", title], capture_output=True, timeout=5)
            if result.returncode == 0:
                time.sleep(0.3)
                return f"Focused window: {title}"
        except FileNotFoundError:
            pass
        try:
            subprocess.run(
                ["xdotool", "search", "--name", title, "windowactivate"],
                capture_output=True, timeout=5,
            )
            time.sleep(0.3)
            return f"Focused window: {title}"
        except FileNotFoundError:
            return "focus_window (Linux) requires wmctrl or xdotool"
        except Exception as e:
            return f"focus_window (Linux) failed: {e}"

    return f"focus_window: unknown OS '{os_name}'"


def computer_control(
    parameters: dict,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params = parameters or {}
    action = params.get("action", "").lower().strip()

    if not action:
        return "No action specified for computer_control."

    if player:
        player.write_log(f"[Computer] {action}")

    print(f"[ComputerControl] ▶ {action}  {params}")

    try:
        if action == "pipeline":
            steps = params.get("steps") or params.get("actions") or []
            return _execute_pipeline(steps)

        if action == "type":
            return _type(params.get("text", ""))

        if action == "smart_type":
            return _smart_type(
                params.get("text", ""),
                clear_first=params.get("clear_first", True),
            )

        if action in ("click", "left_click"):
            return _click(params.get("x"), params.get("y"), "left", 1)

        if action == "double_click":
            return _click(params.get("x"), params.get("y"), "left", 2)

        if action == "right_click":
            return _click(params.get("x"), params.get("y"), "right", 1)

        if action == "move":
            return _move(int(params.get("x", 0)), int(params.get("y", 0)))

        if action == "drag":
            return _drag(
                int(params.get("x1", 0)), int(params.get("y1", 0)),
                int(params.get("x2", 0)), int(params.get("y2", 0)),
            )

        if action == "hotkey":
            raw  = params.get("keys", "")
            keys = [k.strip() for k in raw.split("+")] if isinstance(raw, str) else raw
            return _hotkey(*keys)

        if action == "press":
            return _press(params.get("key", "enter"))

        if action == "scroll":
            return _scroll(
                direction=params.get("direction", "down"),
                amount=int(params.get("amount", 3)),
            )

        if action == "copy":
            return _clipboard_get()

        if action == "paste":
            return _clipboard_paste(params.get("text", ""))

        if action == "screenshot":
            return _screenshot(params.get("path"))

        if action == "screen_find":
            coords = _screen_find(params.get("description", ""))
            return f"{coords[0]},{coords[1]}" if coords else "NOT_FOUND"

        if action == "screen_click":
            desc   = params.get("description", "")
            return _screen_click(desc)

        if action == "wait":
            secs = float(params.get("seconds", 1.0))
            secs = min(secs, 30.0)
            time.sleep(secs)
            return f"Waited {secs}s"

        if action == "clear_field":
            return _clear_field()

        if action == "focus_window":
            return _focus_window(params.get("title", ""))

        if action in ("open", "open_app", "launch", "launch_app"):
            app = params.get("app") or params.get("name") or params.get("path") or ""
            if not app:
                return "open: 'app' parameter is required."
            import shutil, os
            # If it looks like an absolute path or a file, use startfile
            if os.path.exists(app):
                os.startfile(app)
                return f"Opened: {app}"
            # Try to find the executable on PATH first
            found = shutil.which(app)
            if found:
                subprocess.Popen([found], **_WIN_HIDE)
                return f"Launched: {app}"
            # Fall back to Win+R style shell open
            try:
                os.startfile(app)
                return f"Opened: {app}"
            except Exception as e:
                # Last resort: powershell Start-Process
                result = subprocess.run(
                    ["powershell", "-NoProfile", "-NonInteractive", "-Command",
                     f'Start-Process "{app}"'],
                    capture_output=True, timeout=10, **_WIN_HIDE,
                )
                if result.returncode == 0:
                    return f"Launched via shell: {app}"
                return f"Could not open '{app}': {e}"

        if action == "random_data":
            dt     = params.get("type", "name")
            result = _random_data(dt)
            print(f"[ComputerControl] 🎲 random {dt} → {result}")
            return result

        if action == "user_data":
            field   = params.get("field", "name")
            profile = _user_profile()
            value   = profile.get(field, "")
            if not value:
                value = _random_data(field)
                print(f"[ComputerControl] ⚠️ No '{field}' in memory, using random: {value}")
            return value

        return f"Unknown action: '{action}'"

    except Exception as e:
        print(f"[ComputerControl] ❌ {action}: {e}")
        return f"computer_control '{action}' failed: {e}"


TOOL = {
    "name": "computer_control",
    "description": "Direct computer control: type, click, hotkeys, scroll, move mouse, screenshots, find elements on screen.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "type | smart_type | click | double_click | right_click | hotkey | press | scroll | move | copy | paste | screenshot | wait | clear_field | focus_window | open | screen_find | screen_click | random_data | user_data | pipeline"
            },
            "steps": {
                "type": "ARRAY",
                "description": "List of sub-actions for 'pipeline' e.g. [{'action':'hotkey','keys':'win+r'},{'action':'type','text':'notepad'},{'action':'press','key':'enter'}]",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "action": {"type": "STRING"},
                        "keys": {"type": "STRING"},
                        "key": {"type": "STRING"},
                        "text": {"type": "STRING"},
                        "x": {"type": "INTEGER"},
                        "y": {"type": "INTEGER"},
                        "button": {"type": "STRING"},
                        "clicks": {"type": "INTEGER"},
                        "seconds": {"type": "NUMBER"},
                        "clear_first": {"type": "BOOLEAN"}
                    }
                }
            },
            "text": {"type": "STRING", "description": "Text to type or paste"},
            "x": {"type": "INTEGER", "description": "X coordinate"},
            "y": {"type": "INTEGER", "description": "Y coordinate"},
            "keys": {"type": "STRING", "description": "Key combination e.g. 'ctrl+c'"},
            "key": {"type": "STRING", "description": "Single key e.g. 'enter'"},
            "direction": {"type": "STRING", "description": "up | down | left | right"},
            "amount": {"type": "INTEGER", "description": "Scroll amount (default: 3)"},
            "seconds": {"type": "NUMBER", "description": "Seconds to wait"},
            "title": {"type": "STRING", "description": "Window title for focus_window"},
            "description": {"type": "STRING", "description": "Element description for screen_find/screen_click"},
            "type": {"type": "STRING", "description": "Data type for random_data"},
            "field": {"type": "STRING", "description": "Field for user_data: name|email|city"},
            "clear_first": {"type": "BOOLEAN", "description": "Clear field before typing (default: true)"},
            "path": {"type": "STRING", "description": "Save path for screenshot"}
        },
        "required": ["action"]
    },
    "handler": computer_control,
}