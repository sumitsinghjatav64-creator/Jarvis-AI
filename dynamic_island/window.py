"""
window.py
PyQt6 Transparent Desktop Overlay for Apple-Grade Dynamic Island HUD.
Features hardware-accelerated WebEngine, bezel slide-down spring animation,
smart focus auto-hiding when main assistant UI is open, and zero-flicker glass transparency.
"""
import ctypes
import sys
from pathlib import Path

from PyQt6.QtCore import (
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    QRect,
    QTimer,
    Qt,
    QUrl,
    pyqtSlot
)
from PyQt6.QtGui import QColor
from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QApplication, QMainWindow

from config import (
    ASSISTANT_WINDOW_TITLES,
    CONTINUOUS_FLOATING_DEFAULT,
    HIDDEN_Y_OFFSET,
    HIDE_WHEN_ASSISTANT_FOCUSED,
    LOCAL_SERVER_PORT,
    RESTING_Y_OFFSET,
    WINDOW_FOCUS_POLL_INTERVAL_MS
)

class ConsoleWebPage(QWebEnginePage):
    """Custom WebEnginePage that logs JS console output and auto-grants mic permissions."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.featurePermissionRequested.connect(self._handle_permission)

    def _handle_permission(self, securityOrigin, feature):
        self.setFeaturePermission(securityOrigin, feature, QWebEnginePage.PermissionPolicy.PermissionGrantedByUser)

    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceId):
        level_name = getattr(level, "name", str(level))
        print(f"[Island HUD JS {level_name}] L{lineNumber}: {message}")

class DynamicIslandWindow(QMainWindow):
    """
    Transparent, frameless, always-on-top desktop window
    pinned to the top-center of the primary monitor.
    """

    def __init__(self, port: int = LOCAL_SERVER_PORT, continuous_floating: bool = CONTINUOUS_FLOATING_DEFAULT):
        super().__init__()
        self.port = port
        self.continuous_floating = continuous_floating
        self._is_assistant_focused = False

        # 1. Window Flags for clean floating HUD
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.SubWindow |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        # 2. Geometry Calculation (Top-Center of Primary Screen)
        screen = QApplication.primaryScreen().geometry()
        self.hud_width = 620
        self.hud_height = 440
        self.center_x = (screen.width() - self.hud_width) // 2
        self.resting_y = RESTING_Y_OFFSET
        self.hidden_y = HIDDEN_Y_OFFSET

        initial_y = self.resting_y if self.continuous_floating else self.hidden_y
        self.setGeometry(self.center_x, initial_y, self.hud_width, self.hud_height)

        # 3. Setup Hardware-Accelerated WebEngine
        self.browser = QWebEngineView(self)
        self.web_page = ConsoleWebPage(self.browser)
        self.browser.setPage(self.web_page)
        self.browser.setStyleSheet("background: transparent;")
        self.browser.page().setBackgroundColor(Qt.GlobalColor.transparent)

        # Configure WebEngine settings for smooth 60fps animations
        settings = self.browser.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.Accelerated2dCanvasEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)

        self.setCentralWidget(self.browser)
        self.browser.setUrl(QUrl(f"http://127.0.0.1:{self.port}"))

        # 4. Bezel Slide Animation Setup
        self.anim = QPropertyAnimation(self, b"geometry")
        self.anim.setDuration(420)
        self.anim.setEasingCurve(QEasingCurve.Type.OutBack)  # Apple-like elastic overshoot

        # 5. Smart Focus Monitor: Auto-hide when main assistant UI is in foreground
        if HIDE_WHEN_ASSISTANT_FOCUSED and sys.platform == "win32":
            self._focus_timer = QTimer(self)
            self._focus_timer.setInterval(WINDOW_FOCUS_POLL_INTERVAL_MS)
            self._focus_timer.timeout.connect(self._check_active_window_focus)
            self._focus_timer.start()

    def _check_active_window_focus(self):
        """
        Polls the active foreground window.
        When Mark-LV's main UI is focused -> Island auto-retracts into the bezel.
        When Mark-LV is minimized or another app is focused -> Island drops down/appears!
        """
        try:
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return

            # Ignore events if our own HUD window has focus
            if hwnd == int(self.winId()):
                return

            length = user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return

            buff = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buff, length + 1)
            title = buff.value.lower()

            # NEVER treat code editors, IDEs, terminals, or explorer as the assistant UI
            is_editor_or_tool = any(k in title for k in [
                "visual studio code", "vscode", "code -", "powershell",
                "cmd.exe", "terminal", "pycharm", "sublime", "explorer"
            ])

            # Check if this is truly the native assistant window
            is_asst = False
            if not is_editor_or_tool:
                is_asst = any(k in title for k in ASSISTANT_WINDOW_TITLES)

            if is_asst and not self._is_assistant_focused:
                # Main assistant UI came into foreground -> hide island to avoid clutter
                self._is_assistant_focused = True
                self.trigger_retract(force=True)
            elif not is_asst and self._is_assistant_focused:
                # Switched back to editor/other app or assistant minimized -> restore island
                self._is_assistant_focused = False
                if self.continuous_floating:
                    self.trigger_drop_down()
        except Exception:
            pass

    def trigger_drop_down(self):
        """Drops the island down from above the top bezel."""
        self.anim.stop()
        start_rect = self.geometry()
        end_rect = QRect(self.center_x, self.resting_y, self.hud_width, self.hud_height)
        self.anim.setStartValue(start_rect)
        self.anim.setEndValue(end_rect)
        self.anim.start()

    def trigger_retract(self, force: bool = False):
        """Retracts the island back up above the screen into the top bezel."""
        if force or not self.continuous_floating:
            self.anim.stop()
            start_rect = self.geometry()
            end_rect = QRect(self.center_x, self.hidden_y, self.hud_width, self.hud_height)
            self.anim.setStartValue(start_rect)
            self.anim.setEndValue(end_rect)
            self.anim.start()

    def toggle_continuous_floating(self, enabled: bool):
        self.continuous_floating = enabled
        if self.continuous_floating and not self._is_assistant_focused:
            self.trigger_drop_down()
        else:
            self.trigger_retract(force=True)
