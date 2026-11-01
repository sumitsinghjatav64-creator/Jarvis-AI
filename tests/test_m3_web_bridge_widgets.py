"""
tests/test_m3_web_bridge_widgets.py
Comprehensive test suite for Milestone 3: Bi-directional WebBridge Communication & Widget Dispatch.
Validates helper methods, outbound broadcasts, active widget tracking, reconnection replay,
inbound widget action routing, Qt invoker marshalling, malformed input tolerance, and concurrent dispatch.
"""
from __future__ import annotations

import concurrent.futures
import json
import time
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication

import web_bridge
from web_bridge import WebUIBridge

# Ensure Request is present in web_bridge globals for route compilation
from fastapi import Request as _FastAPIRequest
if not hasattr(web_bridge, "Request"):
    web_bridge.Request = _FastAPIRequest


# ---------------------------------------------------------------------------
# Qt and Bridge Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def qapp():
    """Ensure a singleton QApplication instance exists for QObject operations."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(["mark_lv_m3_test"])
    return app


class MockWindow(QObject):
    """Mock Qt window object matching WebUIBridge expectations."""
    _cam_stream_sig = pyqtSignal(bool)
    _cam_frame_sig = pyqtSignal(bytes)

    def __init__(self):
        super().__init__()
        self.hud = MagicMock()
        self.hud.state = "LISTENING"
        self.on_voice_change = MagicMock()
        self._on_setup_done = MagicMock()
        self._open_remote = MagicMock()
        self._open_customize = MagicMock()
        self._open_audio_devices = MagicMock()
        self._open_memory_panel = MagicMock()
        self._open_plugin_manager = MagicMock()
        self._open_plugin_settings = MagicMock()
        self._show_setup = MagicMock()
        self._create_desktop_shortcut = MagicMock()
        self._toggle_autostart = MagicMock()
        self._toggle_brief = MagicMock()
        self._toggle_wake_word = MagicMock()
        self._tap_wake_manual = MagicMock()
        self._tap_enroll_voice = MagicMock()
        self._toggle_voice_filter = MagicMock()
        self._toggle_single_turn = MagicMock()
        self._toggle_ptt = MagicMock()
        self._restart_app = MagicMock()
        self.show = MagicMock()
        self.hide = MagicMock()
        self.raise_ = MagicMock()
        self.activateWindow = MagicMock()


@pytest.fixture
def mock_ui(qapp):
    """Creates a mock UI structure suitable for WebUIBridge."""
    ui = MagicMock()
    ui._win = MockWindow()
    ui.assistant_name = "JARVIS"
    ui.muted = False
    ui.write_log = MagicMock()
    ui.set_state = MagicMock()
    ui.set_audio_level = MagicMock()
    ui.show_content = MagicMock()
    ui.show_confirm = MagicMock()
    ui.hide_confirm = MagicMock()
    ui.on_text_command = MagicMock()
    ui.on_interrupt = MagicMock()
    ui.start_camera_stream = MagicMock()
    ui.stop_camera_stream = MagicMock()
    return ui


@pytest.fixture
def bridge(mock_ui):
    """Instantiates WebUIBridge with mocked UI."""
    return WebUIBridge(mock_ui, host="127.0.0.1", port=8765)


@pytest.fixture
def client(bridge):
    """FastAPI TestClient fixture configured for WebUIBridge."""
    return TestClient(bridge.app, base_url="http://127.0.0.1:8765")


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------

def test_render_widget_dispatch_and_ws_broadcast(client, bridge):
    """Verify render_widget validates input, tracks in active widgets, and broadcasts to WebSocket."""
    with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as ws:
        _ = ws.receive_json()  # init
        _ = ws.receive_json()  # todo_list

        # 1. Render valid widget specification
        ok = bridge.render_widget({
            "id": "status_card",
            "template": "telemetry",
            "title": "System Status",
            "icon": "cpu",
            "target": "dock",
            "data": {"cpu": 12.5, "mem": 45.0},
            "actions": [{"action_id": "refresh", "label": "Refresh"}]
        })
        assert ok is True

        # Receive broadcasted widget_render frame
        msg = ws.receive_json()
        assert msg["type"] == "widget_render"
        assert msg["widget"]["id"] == "status_card"
        assert msg["widget"]["template"] == "telemetry"
        assert msg["widget"]["data"]["cpu"] == 12.5
        assert msg["widget"]["target"] == "dock"

        # Verify tracked in active widgets
        with bridge._widgets_lock:
            assert "status_card" in bridge._active_widgets
            assert bridge._active_widgets["status_card"]["template"] == "telemetry"

        # 2. Render without ID auto-generates unique string ID
        ok2 = bridge.render_widget({"title": "Auto ID Widget", "template": "custom"})
        assert ok2 is True
        msg2 = ws.receive_json()
        assert msg2["type"] == "widget_render"
        assert isinstance(msg2["widget"]["id"], str)
        assert msg2["widget"]["id"].startswith("widget_")

        # 3. Invalid inputs return False and do not broadcast
        assert bridge.render_widget(None) is False
        assert bridge.render_widget("not_a_dict") is False
        assert bridge.render_widget([1, 2, 3]) is False


def test_update_widget_dispatch_and_ws_broadcast(client, bridge):
    """Verify update_widget merges incremental state into active widget and broadcasts update."""
    bridge.render_widget({"id": "metric_card", "data": {"cpu": 10, "mem": 20}})

    with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as ws:
        _ = ws.receive_json()  # init
        _ = ws.receive_json()  # todo_list
        _ = ws.receive_json()  # replayed metric_card

        # 1. Update widget state
        ok = bridge.update_widget("metric_card", {"cpu": 45, "disk": 70})
        assert ok is True

        msg = ws.receive_json()
        assert msg["type"] == "widget_update"
        assert msg["widget_id"] == "metric_card"
        assert msg["data"] == {"cpu": 45, "disk": 70}

        # Verify internal active_widgets merged state under lock
        with bridge._widgets_lock:
            active_data = bridge._active_widgets["metric_card"]["data"]
            assert active_data["cpu"] == 45
            assert active_data["mem"] == 20
            assert active_data["disk"] == 70

        # 2. Invalid inputs return False
        assert bridge.update_widget("", {"cpu": 50}) is False
        assert bridge.update_widget("metric_card", "not_a_dict") is False
        assert bridge.update_widget("metric_card", None) is False
        assert bridge.update_widget(None, {"cpu": 50}) is False


def test_dismiss_widget_dispatch_and_ws_broadcast(client, bridge):
    """Verify dismiss_widget evicts widget from active registry and broadcasts dismissal."""
    bridge.render_widget({"id": "card_to_dismiss", "data": {}})

    with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as ws:
        _ = ws.receive_json()  # init
        _ = ws.receive_json()  # todo_list
        _ = ws.receive_json()  # replayed card_to_dismiss

        ok = bridge.dismiss_widget("card_to_dismiss")
        assert ok is True

        msg = ws.receive_json()
        assert msg["type"] == "widget_dismiss"
        assert msg["widget_id"] == "card_to_dismiss"

        # Verify evicted from active_widgets
        with bridge._widgets_lock:
            assert "card_to_dismiss" not in bridge._active_widgets

        # Invalid inputs return False
        assert bridge.dismiss_widget("") is False
        assert bridge.dismiss_widget(None) is False
        assert bridge.dismiss_widget(123) is False


def test_clear_all_widgets_dispatch_and_ws_broadcast(client, bridge):
    """Verify clear_all_widgets clears active registry and broadcasts widget_clear_all."""
    bridge.render_widget({"id": "dock_w", "target": "dock"})
    bridge.render_widget({"id": "chat_w", "target": "chat"})

    with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as ws:
        _ = ws.receive_json()  # init
        _ = ws.receive_json()  # todo_list
        _ = ws.receive_json()  # replayed dock_w
        _ = ws.receive_json()  # replayed chat_w

        # 1. Clear only target='dock'
        ok = bridge.clear_all_widgets(target="dock", immediate=True)
        assert ok is True

        msg = ws.receive_json()
        assert msg["type"] == "widget_clear_all"
        assert msg["target"] == "dock"
        assert msg["immediate"] is True
        assert msg["options"]["immediate"] is True

        # Verify dock_w evicted but chat_w remains
        with bridge._widgets_lock:
            assert "dock_w" not in bridge._active_widgets
            assert "chat_w" in bridge._active_widgets

        # 2. Clear all targets via clear_widgets alias
        ok2 = bridge.clear_widgets()
        assert ok2 is True

        msg2 = ws.receive_json()
        assert msg2["type"] == "widget_clear_all"
        assert msg2["target"] is None

        with bridge._widgets_lock:
            assert len(bridge._active_widgets) == 0


def test_broadcast_telemetry(client, bridge):
    """Verify broadcast_telemetry broadcasts metrics and propagates to active telemetry widgets."""
    bridge.render_widget({"id": "live_telemetry", "template": "telemetry", "data": {"cpu": 5}})

    with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as ws:
        _ = ws.receive_json()  # init
        _ = ws.receive_json()  # todo_list
        _ = ws.receive_json()  # replayed live_telemetry

        ok = bridge.broadcast_telemetry({"cpu": 42.0, "mem": 68.5, "gpu": 80.0})
        assert ok is True

        # Receives metrics broadcast
        msg1 = ws.receive_json()
        assert msg1["type"] == "metrics"
        assert msg1["cpu"] == 42.0
        assert msg1["mem"] == 68.5
        assert msg1["gpu"] == 80.0

        # Receives synchronized widget_update for live_telemetry widget
        msg2 = ws.receive_json()
        assert msg2["type"] == "widget_update"
        assert msg2["widget_id"] == "live_telemetry"
        assert msg2["data"]["cpu"] == 42.0

        # Non-dict metrics rejected
        assert bridge.broadcast_telemetry("invalid") is False
        assert bridge.broadcast_telemetry(None) is False


def test_zero_clients_dispatch_safety(bridge):
    """Verify that calling dispatch helpers with 0 clients connected returns cleanly without raising."""
    assert bridge.render_widget({"id": "orphan", "template": "custom"}) is True
    assert bridge.update_widget("orphan", {"foo": "bar"}) is True
    assert bridge.dismiss_widget("orphan") is True
    assert bridge.clear_all_widgets() is True
    assert bridge.broadcast_telemetry({"cpu": 10}) is True
    bridge.broadcast({"type": "custom_event"})
    # No exceptions raised


def test_inbound_widget_action_routing_to_registered_handler(client, bridge):
    """Verify inbound widget_action routes to registered handlers supporting variable callback signatures."""
    calls_3args = []
    calls_2args = []
    calls_1arg = []

    bridge.register_action_handler("refresh", lambda wid, act, pld: calls_3args.append((wid, act, pld)))
    bridge.register_action_handler("toggle", lambda wid, pld: calls_2args.append((wid, pld)))
    bridge.register_action_handler("ping", lambda pld: calls_1arg.append(pld))

    with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as ws:
        _ = ws.receive_json()
        _ = ws.receive_json()

        ws.send_json({"type": "widget_action", "widget_id": "card_a", "action_id": "refresh", "payload": {"force": True}})
        ws.send_json({"type": "widget_action", "widget_id": "card_b", "action_id": "toggle", "payload": {"active": True}})
        ws.send_json({"type": "widget_action", "widget_id": "card_c", "action_id": "ping", "payload": {"echo": 123}})
        ws.send_json({"type": "interrupt"})

    assert len(calls_3args) == 1
    assert calls_3args[0] == ("card_a", "refresh", {"force": True})

    assert len(calls_2args) == 1
    assert calls_2args[0] == ("card_b", {"active": True})

    assert len(calls_1arg) == 1
    assert calls_1arg[0] == {"echo": 123}

    # Test unregistering handler
    bridge.unregister_action_handler("refresh")
    calls_3args.clear()
    with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as ws:
        _ = ws.receive_json()
        _ = ws.receive_json()
        ws.send_json({"type": "widget_action", "widget_id": "card_a", "action_id": "refresh", "payload": {}})
        ws.send_json({"type": "interrupt"})
    assert len(calls_3args) == 0


def test_inbound_widget_action_routing_with_qt_invoker(client, bridge, qapp):
    """Verify inbound widget_action with run_on_qt_thread=True dispatches via Qt invoker."""
    invoked = []
    bridge.register_action_handler(
        "qt_action",
        lambda wid, act, pld: invoked.append((wid, act, pld)),
        run_on_qt_thread=True,
    )

    with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as ws:
        _ = ws.receive_json()
        _ = ws.receive_json()
        ws.send_json({
            "type": "widget_action",
            "widget_id": "sys_panel",
            "action_id": "qt_action",
            "payload": {"cmd": "open"}
        })
        ws.send_json({"type": "interrupt"})

    qapp.processEvents()
    assert len(invoked) == 1
    assert invoked[0] == ("sys_panel", "qt_action", {"cmd": "open"})


def test_inbound_widget_action_routing_to_ui_delegate(client, bridge, mock_ui):
    """Verify inbound widget_action invokes ui.on_widget_action and bridge delegate hooks."""
    mock_ui.on_widget_action = MagicMock()
    bridge_delegate = MagicMock()
    bridge.set_widget_action_handler(bridge_delegate)

    with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as ws:
        _ = ws.receive_json()
        _ = ws.receive_json()
        ws.send_json({
            "type": "widget_action",
            "widget_id": "w_delegate",
            "action_id": "calibrate",
            "payload": {"step": 2}
        })
        ws.send_json({"type": "interrupt"})

    mock_ui.on_widget_action.assert_called_once_with("w_delegate", "calibrate", {"step": 2})
    bridge_delegate.assert_called_once_with("w_delegate", "calibrate", {"step": 2})


def test_inbound_widget_action_malformed_tolerance(client, bridge):
    """Verify resilience when encountering malformed or adversarial inbound widget_action messages."""
    with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as ws:
        _ = ws.receive_json()
        _ = ws.receive_json()

        # Missing widget_id
        ws.send_json({"type": "widget_action", "action_id": "act"})

        # Missing action_id
        ws.send_json({"type": "widget_action", "widget_id": "w1"})

        # Missing both
        ws.send_json({"type": "widget_action"})

        # Non-dict payload
        ws.send_json({"type": "widget_action", "widget_id": "w1", "action_id": "act", "payload": "string_not_dict"})
        ws.send_json({"type": "widget_action", "widget_id": "w1", "action_id": "act", "payload": 12345})
        ws.send_json({"type": "widget_action", "widget_id": "w1", "action_id": "act", "payload": [1, 2, 3]})

        # Non-dict root JSON message
        ws.send_text(json.dumps(["not", "a", "dict"]))
        ws.send_text(json.dumps("plain string"))
        ws.send_text(json.dumps(12345))

        # Giant 64KB string inside payload dict
        huge = {"type": "widget_action", "widget_id": "w_huge", "action_id": "huge_act", "payload": {"big": "X" * 65536}}
        ws.send_text(json.dumps(huge))

        # XSS and hostile characters
        xss = {
            "type": "widget_action",
            "widget_id": "<script>alert('xss')</script>",
            "action_id": "'; DROP TABLE widgets; --",
            "payload": {"html": "<img src=x onerror=alert(1)>"}
        }
        ws.send_text(json.dumps(xss))

        # Built-in dismiss eviction test
        bridge.render_widget({"id": "w_to_dismiss_by_act"})
        with bridge._widgets_lock:
            assert "w_to_dismiss_by_act" in bridge._active_widgets
        ws.send_json({"type": "widget_action", "widget_id": "w_to_dismiss_by_act", "action_id": "dismiss", "payload": {}})

        # Verify bridge remains healthy by sending a normal interrupt command
        ws.send_json({"type": "interrupt"})

    with bridge._widgets_lock:
        assert "w_to_dismiss_by_act" not in bridge._active_widgets


def test_active_widget_tracking_and_reconnection_replay(client, bridge):
    """Verify active widgets are tracked and replayed upon new or reconnected client sessions."""
    # 1. Render active widgets
    bridge.render_widget({"id": "w_active_1", "title": "Widget 1", "template": "telemetry", "data": {"cpu": 10}})
    bridge.render_widget({"id": "w_active_2", "title": "Widget 2", "template": "action_grid", "data": {"state": "OK"}})

    # 2. Update widget 1 state
    bridge.update_widget("w_active_1", {"cpu": 25, "ram": 50})

    # 3. Connect client 1 -> receives init, todo_list, and active widget replays
    with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as ws:
        msg1 = ws.receive_json()
        assert msg1["type"] == "init"
        msg2 = ws.receive_json()
        assert msg2["type"] == "todo_list"

        msg3 = ws.receive_json()
        msg4 = ws.receive_json()
        replayed = {msg3["widget"]["id"]: msg3["widget"], msg4["widget"]["id"]: msg4["widget"]}
        assert "w_active_1" in replayed
        assert "w_active_2" in replayed
        assert replayed["w_active_1"]["data"] == {"cpu": 25, "ram": 50}

    # 4. Dismiss widget 2
    bridge.dismiss_widget("w_active_2")

    # 5. Connect client 2 -> only remaining active widget 1 is replayed
    with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as ws:
        msg1 = ws.receive_json()
        assert msg1["type"] == "init"
        msg2 = ws.receive_json()
        assert msg2["type"] == "todo_list"

        msg3 = ws.receive_json()
        assert msg3["type"] == "widget_render"
        assert msg3["widget"]["id"] == "w_active_1"


def test_multithreaded_concurrent_widget_dispatch(bridge):
    """Verify multithreaded dispatch safety with 50 concurrent threads executing bridge helpers."""
    num_threads = 50
    errors = []

    def worker(worker_id: int):
        try:
            wid = f"concurrent_widget_{worker_id}"
            # Render
            ok = bridge.render_widget({
                "id": wid,
                "template": "telemetry",
                "title": f"Telemetry {worker_id}",
                "data": {"value": worker_id}
            })
            if not ok:
                errors.append(f"worker {worker_id} render failed")

            # Update
            ok = bridge.update_widget(wid, {"value": worker_id * 10, "state": "active"})
            if not ok:
                errors.append(f"worker {worker_id} update failed")

            # Telemetry broadcast
            bridge.broadcast_telemetry({"cpu": float(worker_id)})

            # Dismiss
            ok = bridge.dismiss_widget(wid)
            if not ok:
                errors.append(f"worker {worker_id} dismiss failed")
        except Exception as exc:
            errors.append(f"worker {worker_id} exception: {exc}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker, i) for i in range(num_threads)]
        concurrent.futures.wait(futures)
        for f in futures:
            f.result()

    assert len(errors) == 0, f"Concurrent dispatch encountered errors: {errors}"


def test_hooked_ui_methods_delegation(bridge, mock_ui):
    """Verify methods bound to self.ui delegate to WebUIBridge helpers."""
    assert hasattr(mock_ui, "render_widget")
    assert hasattr(mock_ui, "update_widget")
    assert hasattr(mock_ui, "dismiss_widget")
    assert hasattr(mock_ui, "clear_all_widgets")
    assert hasattr(mock_ui, "clear_widgets")
    assert hasattr(mock_ui, "broadcast_telemetry")
    assert hasattr(mock_ui, "register_action_handler")

    # Test execution via mock_ui
    ok = mock_ui.render_widget({"id": "ui_hook_test", "template": "activity_tracker", "data": {}})
    assert ok is True
    with bridge._widgets_lock:
        assert "ui_hook_test" in bridge._active_widgets

    ok = mock_ui.update_widget("ui_hook_test", {"progress": 75})
    assert ok is True
    with bridge._widgets_lock:
        assert bridge._active_widgets["ui_hook_test"]["data"]["progress"] == 75

    ok = mock_ui.dismiss_widget("ui_hook_test")
    assert ok is True
    with bridge._widgets_lock:
        assert "ui_hook_test" not in bridge._active_widgets
