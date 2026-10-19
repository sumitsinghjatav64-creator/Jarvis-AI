"""
MARK XL — Dependency verification.

Called on launch and after engine reconfiguration.
Verifies packages are present and fails fast with instructions if missing,
decoupling package management from application runtime.
"""
from __future__ import annotations

import importlib.util
import platform
import sys
from typing import Callable

# ── Package lists ─────────────────────────────────────────────────────────
# Each entry: (import_name, pip_package_name)

_CORE: list[tuple[str, str]] = [
    ("psutil",             "psutil"),
    ("PIL",                "pillow"),
    ("sounddevice",        "sounddevice"),
    ("numpy",              "numpy"),
    ("requests",           "requests"),
    ("bs4",                "beautifulsoup4"),
    ("ddgs",               "ddgs"),
    ("pyautogui",          "pyautogui"),
    ("pyperclip",          "pyperclip"),
    ("pygetwindow",        "pygetwindow"),
    ("mss",                "mss"),
    ("cv2",                "opencv-python"),
    ("soundfile",          "soundfile"),
    ("miniaudio",          "miniaudio"),
    ("send2trash",         "send2trash"),
    ("pptx",               "python-pptx"),
    ("youtube_transcript_api", "youtube-transcript-api"),
    ("playwright",         "playwright"), # Added to core check
]

_WINDOWS: list[tuple[str, str]] = [
    ("comtypes",   "comtypes"),
    ("pycaw",      "pycaw"),
    ("win10toast", "win10toast"),
    ("pywinauto",  "pywinauto"),
]

_STT: dict[str, list[tuple[str, str]]] = {
    "whisper": [("faster_whisper", "faster-whisper")],
    "vosk":    [("vosk",           "vosk")],
}

_TTS: dict[str, list[tuple[str, str]]] = {
    "edgetts":    [("edge_tts", "edge-tts")],
    "kokoro":     [("kokoro",   "kokoro>=0.9"), ("soundfile", "soundfile")],
    "elevenlabs": [],   
}

# ── Helpers ───────────────────────────────────────────────────────────────

def _available(module: str) -> bool:
    """Return True if the module can be imported (no actual import)."""
    return importlib.util.find_spec(module) is not None

# ── Public API ────────────────────────────────────────────────────────────

def verify_dependencies(config: dict, log: Callable | None = None) -> bool:
    """
    Verify all missing packages required by *config*.
    Returns True if all dependencies are satisfied, False otherwise.
    """
    stt = config.get("stt_engine", "whisper").lower()
    tts = config.get("tts_engine", "edgetts").lower()

    needed: list[tuple[str, str]] = list(_CORE)
    needed += _STT.get(stt, [])
    needed += _TTS.get(tts, [])
    if platform.system() == "Windows":
        needed += _WINDOWS

    # Deduplicate
    seen: set[str] = set()
    unique: list[tuple[str, str]] = []
    for mod, pkg in needed:
        if pkg not in seen:
            seen.add(pkg)
            unique.append((mod, pkg))

    missing_pip = [pkg for mod, pkg in unique if not _available(mod)]

    if not missing_pip:
        if log:
            log("SYS: All dependencies verified ✓")
        return True

    # Build the exact command the user needs to run
    pkg_names = " ".join(missing_pip)
    error_msg = f"CRITICAL: Missing dependencies. Please exit and run:\n  pip install {pkg_names}"
    
    if "playwright" in missing_pip:
        error_msg += "\n  python -m playwright install chromium"

    if log:
        log(error_msg)
    
    return False