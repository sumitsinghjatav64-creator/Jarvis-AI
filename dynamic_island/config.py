"""
Configuration for Dynamic Island AI Companion & Jev-Ultrafast.
"""
from dataclasses import dataclass
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"

# Bridge Mode:
# 'standalone' -> Uses internal mock event pump & test controls (zero dependency on Mark-LV)
# 'live'       -> Connects to Mark-LV at ws://127.0.0.1:8765/ws
BRIDGE_MODE = "live"
MARK_LV_WS_URI = "ws://127.0.0.1:8765/ws"

# Server Ports
LOCAL_SERVER_PORT = 8768

# Wake Word & Addressing
WAKE_WORDS = ["bixy", "bixi", "hey bixy"]
ASSISTANT_NAME = "Bixy"

# Floating & Positioning
CONTINUOUS_FLOATING_DEFAULT = True  # If False, stays retracted above monitor until 'Bixy' is triggered
RESTING_Y_OFFSET = 12               # Pixels from top edge of primary screen
HIDDEN_Y_OFFSET = -180              # Pixels above screen fold for stealth mode

# Smart Focus Management:
# Automatically hides the island when the main assistant window is active/focused,
# and shows it when the assistant is minimized or another application is active.
HIDE_WHEN_ASSISTANT_FOCUSED = True
ASSISTANT_WINDOW_TITLES = ["bixy -", "jarvis -", "bixy ai", "jarvis ai"]
WINDOW_FOCUS_POLL_INTERVAL_MS = 300

# Spring Physics Settings (Apple-like feel)
SPRING_STIFFNESS = 380.0
SPRING_DAMPING = 28.0
SPRING_MASS = 1.0

# Jev-Ultrafast Settings
TYPESAFE_API_KEY = ""               # Optional: set via environment or config
USE_JEV_SIMULATION = True           # Falls back to high-speed deterministic local simulation if no key
