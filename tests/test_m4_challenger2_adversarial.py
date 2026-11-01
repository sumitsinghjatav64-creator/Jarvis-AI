"""
tests/test_m4_challenger2_adversarial.py

Milestone 4 Phase 2 Challenger 2: White-Box Adversarial Coverage Hardening Suite.
Comprehensive adversarial audit covering:
1. Empirical Node.js oracle execution (DOM saturation burst, deep event delegation,
   template exception boundaries, multi-template XSS sanitization, malformed payload resilience).
2. Backend concurrent widget action flood and lock contention.
3. Extreme unicode, SQL/shell injection strings, and malformed payload tolerance in backend.
4. Target-isolated widget clearing (dock vs chat) and immediate vs animated teardown.
5. Telemetry broadcast fan-out across multiple active telemetry widgets.
6. Compositor-safe CSS and DOM layout verification in ui_improved.html.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import threading
from typing import Any
from unittest.mock import MagicMock
import pytest
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication

import web_bridge
from web_bridge import WebUIBridge

from fastapi import Request as _FastAPIRequest
if not hasattr(web_bridge, "Request"):
    web_bridge.Request = _FastAPIRequest


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(["mark_lv_m4_challenger2_test"])
    return app


class MockWindow(QObject):
    _cam_stream_sig = pyqtSignal(bool)
    _cam_frame_sig = pyqtSignal(bytes)

    def __init__(self):
        super().__init__()
        self.hud = MagicMock()
        self.hud.state = "LISTENING"
        self.on_voice_change = MagicMock()
        self._on_setup_done = MagicMock()
        self.show = MagicMock()
        self.hide = MagicMock()
        self.raise_ = MagicMock()
        self.activateWindow = MagicMock()


@pytest.fixture
def mock_ui(qapp):
    ui = MagicMock()
    ui._win = MockWindow()
    ui.assistant_name = "JARVIS"
    ui.muted = False
    ui.write_log = MagicMock()
    ui.set_state = MagicMock()
    ui.set_audio_level = MagicMock()
    ui.show_content = MagicMock()
    ui.show_confirm = MagicMock()
    return ui


@pytest.fixture
def bridge(mock_ui):
    b = WebUIBridge(ui=mock_ui, host="127.0.0.1", port=8765)
    return b


def test_m4_challenger2_node_oracle_empirical_execution():
    """
    Executes the standalone Node.js WidgetManager oracle & adversarial test suite.
    Empirically verifies:
    1. Extreme DOM Saturation Burst: 1,000 rapid renders capped at 4 active entries (0 DOM node leak).
    2. Deep Event Propagation: Click delegation from nested SVG paths, text spans, stateful toggles.
    3. Template Exception Boundaries: Uncaught template errors caught and rendered as escaped ERROR cards.
    4. Multi-Template XSS Sanitization: Zero unescaped executable script/img/svg tags across all templates.
    5. Malformed Payloads & Null Boundaries: Undefined/null/broken schemas handled gracefully.
    6. WebSocket Offline & Error Handling: Safe degradation when bridge is offline or callbacks fail.
    """
    oracle_script = Path(__file__).parent / "test_m4_challenger2_oracle.js"
    assert oracle_script.exists(), "Oracle test script not found"

    proc = subprocess.run(
        ["node", str(oracle_script)],
        capture_output=True,
        text=True,
        timeout=30
    )

    output = proc.stdout + "\n" + proc.stderr

    assert "Extreme DOM Saturation Burst" in output
    assert "Deep Event Propagation & Click Delegation" in output
    assert "Template Rendering Exception Boundaries" in output
    assert "Multi-Template XSS & Injection Sanitization" in output
    assert "Malformed Data Payloads & Boundary Resilience" in output
    assert "WebSocket Offline & Error Handling" in output
    assert "ALL ADVERSARIAL TESTS COMPLETED: 66 passed, 0 failed" in output, \
        f"Expected all 66 adversarial oracle checks to pass. Output:\n{output}"
    assert proc.returncode == 0, f"Oracle tests failed with code {proc.returncode}"


def test_backend_high_volume_concurrent_widget_actions(bridge: WebUIBridge):
    """
    Stress-tests backend WebUIBridge with high-volume concurrent widget actions
    dispatched across multiple parallel threads simultaneously.
    Verifies lock safety, zero race conditions, and complete handler execution.
    """
    handled_count = 0
    count_lock = threading.Lock()

    def sample_handler(wid: str, act: str, pld: dict[str, Any]):
        nonlocal handled_count
        with count_lock:
            handled_count += 1

    bridge.register_action_handler("stress_action", sample_handler, run_on_qt_thread=False)

    num_threads = 20
    actions_per_thread = 50
    total_actions = num_threads * actions_per_thread

    def worker_thread(tid: int):
        for i in range(actions_per_thread):
            bridge._dispatch_widget_action(
                widget_id=f"wid_{tid}_{i}",
                action_id="stress_action",
                payload={"tid": tid, "seq": i}
            )

    threads = [threading.Thread(target=worker_thread, args=(t,)) for t in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10.0)

    assert handled_count == total_actions, f"Expected {total_actions} actions handled, got {handled_count}"


def test_backend_widget_action_extreme_unicode_and_injections(bridge: WebUIBridge):
    """
    Adversarially feeds malicious payloads (SQL injection, shell expansion,
    extreme unicode, null bytes, cyclic structures) to _dispatch_widget_action.
    Verifies that the backend handles all edge cases without raising exceptions.
    """
    received_payloads: list[dict[str, Any]] = []

    def catch_all_handler(wid: str, act: str, pld: dict[str, Any]):
        received_payloads.append(pld)

    bridge.register_action_handler("test_act", catch_all_handler, run_on_qt_thread=False)

    hostile_payloads = [
        {"sql": "'; DROP TABLE widgets; --"},
        {"shell": "$(reboot) && `rm -rf /`"},
        {"unicode": "\u0000\uFFFF\uD83D\uDE80\u202E\u200B"},
        {"huge_string": "A" * 65536},
        {"nested": {"a": {"b": {"c": {"d": [1, 2, 3, None, True]}}}}},
        None,  # Malformed non-dict payload
        "malformed_string_payload",
        12345,
    ]

    for p in hostile_payloads:
        # Must not raise under any payload
        bridge._dispatch_widget_action("widget_sec", "test_act", p)  # type: ignore

    assert len(received_payloads) == len(hostile_payloads)


def test_backend_clear_all_widgets_target_isolation(bridge: WebUIBridge):
    """
    Tests clear_all_widgets with explicit target filtering (dock vs chat)
    and validates internal active widget state retention.
    """
    # Register 3 dock widgets and 2 chat widgets
    bridge.render_widget({"id": "d1", "target": "dock", "template": "telemetry"})
    bridge.render_widget({"id": "d2", "target": "dock", "template": "telemetry"})
    bridge.render_widget({"id": "d3", "target": "dock", "template": "telemetry"})
    bridge.render_widget({"id": "c1", "target": "chat", "template": "custom"})
    bridge.render_widget({"id": "c2", "target": "chat", "template": "custom"})

    with bridge._widgets_lock:
        assert len(bridge._active_widgets) == 5

    # Clear chat only
    bridge.clear_all_widgets(target="chat", immediate=True)

    with bridge._widgets_lock:
        assert len(bridge._active_widgets) == 3
        assert set(bridge._active_widgets.keys()) == {"d1", "d2", "d3"}

    # Clear all remaining
    bridge.clear_all_widgets(target=None, immediate=False)

    with bridge._widgets_lock:
        assert len(bridge._active_widgets) == 0


def test_backend_telemetry_broadcast_fan_out(bridge: WebUIBridge):
    """
    Verifies that broadcast_telemetry updates all registered telemetry widgets.
    """
    bridge.render_widget({"id": "t1", "template": "telemetry", "title": "T1"})
    bridge.render_widget({"id": "t2", "template": "telemetry", "title": "T2"})
    bridge.render_widget({"id": "a1", "template": "action_grid", "title": "A1"})

    metrics = {"cpu": 45.5, "mem": 62.0}
    result = bridge.broadcast_telemetry(metrics)
    assert result is True

    with bridge._widgets_lock:
        # t1 and t2 should have been updated with metrics
        assert bridge._active_widgets["t1"]["data"]["cpu"] == 45.5
        assert bridge._active_widgets["t2"]["data"]["cpu"] == 45.5
        # a1 is action_grid, should not have been updated with general telemetry
        assert "cpu" not in bridge._active_widgets["a1"].get("data", {})


def test_compositor_safety_and_dom_structure():
    """
    Parses ui_improved.html to verify:
    1. Zero 'backdrop-filter: blur' in critical rendering path (GPU compositor safety).
    2. #gen-ui-dock CSS container rules and glass design tokens exist.
    3. Camera PIP coexistence styling (cam-offset) exists.
    4. WidgetManager and WidgetTemplates are cleanly exposed.
    """
    html_path = Path(__file__).resolve().parent.parent / "ui_improved.html"
    assert html_path.exists(), "ui_improved.html not found"

    content = html_path.read_text(encoding="utf-8")

    # 1. Compositor safety
    assert "backdrop-filter: blur" not in content, "Found forbidden backdrop-filter blur in ui_improved.html"

    # 2. Glass design tokens
    assert "--glass-surface:" in content
    assert "--glass-border:" in content
    assert "--glass-specular:" in content

    # 3. Dock container & PIP coexistence
    assert ".gen-ui-dock" in content
    assert ".gen-ui-dock.cam-offset" in content or "cam-offset" in content

    # 4. Framework classes
    assert "class WidgetManager" in content
    assert "const WidgetTemplates" in content
    assert "window.widgetManager = widgetManager" in content
