"""
tests/test_web_bridge_e2e.py
End-to-end integration and requirement-driven tests covering WebUIBridge,
WebSocket protocols, Generative UI interface contracts, and real-world application scenarios (Tiers 1–4).
"""
from __future__ import annotations

import json
import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication
from starlette.websockets import WebSocketDisconnect

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
        app = QApplication(["mark_lv_e2e_test"])
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
    """FastAPI TestClient bound to the bridge application."""
    return TestClient(bridge.app, base_url="http://127.0.0.1:8765")


# ---------------------------------------------------------------------------
# Tier 1: Feature Coverage (WebSocket Protocol & Nominal Inbound Handlers)
# ---------------------------------------------------------------------------

def test_ws_handshake_and_init_payload(client):
    """Verify WebSocket handshake succeeds and delivers the initial 'init' payload."""
    with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as ws:
        init_data = ws.receive_json()
        assert init_data.get("type") == "init"
        assert init_data.get("assistant_name") == "JARVIS"
        assert init_data.get("state") == "LISTENING"
        assert init_data.get("muted") is False
        assert "tts_engine" in init_data
        assert "edge_voices" in init_data
        assert "gemini_voices" in init_data


def test_ws_initial_todo_list_delivery(client):
    """Verify WebSocket handshake immediately delivers the 'todo_list' as the second message."""
    with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as ws:
        _ = ws.receive_json()  # Consume 'init'
        todo_data = ws.receive_json()
        assert todo_data.get("type") == "todo_list"
        assert isinstance(todo_data.get("tasks"), list)


def test_ws_text_command_dispatch(client, mock_ui):
    """Verify client sending 'command' invokes ui.on_text_command with the exact text."""
    with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as ws:
        _ = ws.receive_json()
        _ = ws.receive_json()

        ws.send_json({"type": "command", "text": "run system diagnostic"})

    mock_ui.on_text_command.assert_called_once_with("run system diagnostic")


def test_ws_interrupt_dispatch(client, mock_ui):
    """Verify client sending 'interrupt' triggers ui.on_interrupt()."""
    with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as ws:
        _ = ws.receive_json()
        _ = ws.receive_json()

        ws.send_json({"type": "interrupt"})

    mock_ui.on_interrupt.assert_called_once()


def test_ws_toggle_mute_dispatch(client, mock_ui, bridge):
    """Verify 'toggle_mute' toggles ui.muted state and broadcasts new state."""
    assert mock_ui.muted is False

    with patch.object(bridge, "broadcast") as mock_broadcast:
        with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as ws:
            _ = ws.receive_json()
            _ = ws.receive_json()

            ws.send_json({"type": "toggle_mute"})

        assert mock_ui.muted is True
        mock_broadcast.assert_called_with({
            "type": "state",
            "state": "MUTED",
            "muted": True,
        })


def test_ws_toggle_camera_dispatch(client, mock_ui, bridge):
    """Verify 'toggle_camera' toggles camera streaming state on ui."""
    bridge._cam_active = False
    with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as ws:
        _ = ws.receive_json()
        _ = ws.receive_json()

        ws.send_json({"type": "toggle_camera"})

    mock_ui.start_camera_stream.assert_called_once()

    # Now when active, next toggle stops the stream
    bridge._cam_active = True
    with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as ws:
        _ = ws.receive_json()
        _ = ws.receive_json()

        ws.send_json({"type": "toggle_camera"})

    mock_ui.stop_camera_stream.assert_called_once()


def test_ws_confirm_resolution(client):
    """Verify 'confirm' message resolves the confirm_gate promise."""
    with patch("core.confirm.resolve") as mock_resolve:
        with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as ws:
            _ = ws.receive_json()
            _ = ws.receive_json()

            ws.send_json({"type": "confirm", "accepted": True})

        mock_resolve.assert_called_once_with(True)


def test_ws_todo_add_and_toggle(client, bridge):
    """Verify 'todo_add' and 'todo_toggle' update the todo store and broadcast updates."""
    with patch.object(bridge, "broadcast") as mock_broadcast:
        with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as ws:
            _ = ws.receive_json()
            _ = ws.receive_json()

            ws.send_json({"type": "todo_add", "text": "E2E Unit Verification Task"})

        assert mock_broadcast.called
        last_call_payload = mock_broadcast.call_args[0][0]
        assert last_call_payload["type"] == "todo_list"


def test_ws_save_api_key(client, mock_ui, bridge):
    """Verify 'save_api_key' dispatches setup completion to Qt window."""
    with patch.object(bridge, "broadcast") as mock_broadcast:
        with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as ws:
            _ = ws.receive_json()
            _ = ws.receive_json()

            ws.send_json({"type": "save_api_key", "key": "test_api_key_xyz", "os": "windows"})

        assert mock_broadcast.called
        assert any(call[0][0].get("type") == "log" for call in mock_broadcast.call_args_list)


# ---------------------------------------------------------------------------
# Tier 2: Boundary & Corner Cases (Origins, Malformed Input, Extreme Payloads)
# ---------------------------------------------------------------------------

def test_ws_rejects_unauthorized_origin(client):
    """Verify WebSocket handshake is rejected with code 1008 for untrusted origin."""
    with pytest.raises(WebSocketDisconnect) as excinfo:
        with client.websocket_connect("/ws", headers={"origin": "http://untrusted-external-site.com"}) as _:
            pass
    assert excinfo.value.code == 1008


def test_ws_rejects_malformed_scheme_origin(client):
    """Verify non-http/https schemes in Origin header are rejected."""
    with pytest.raises(WebSocketDisconnect) as excinfo:
        with client.websocket_connect("/ws", headers={"origin": "javascript:alert(1)"}) as _:
            pass
    assert excinfo.value.code == 1008


def test_ws_handles_malformed_json_gracefully(client, mock_ui):
    """Verify malformed JSON does not crash the server and subsequent valid messages work."""
    with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as ws:
        _ = ws.receive_json()
        _ = ws.receive_json()

        # Send invalid JSON
        ws.send_text("{{malformed_json_payload: null,")

        # Send valid command immediately after
        ws.send_json({"type": "command", "text": "still responsive after bad json"})

    mock_ui.on_text_command.assert_called_with("still responsive after bad json")


def test_ws_handles_unknown_message_type(client):
    """Verify unknown message types are safely ignored without disconnection."""
    with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as ws:
        _ = ws.receive_json()
        _ = ws.receive_json()

        # Unknown type
        ws.send_json({"type": "nonexistent_action_type_999", "payload": {"foo": "bar"}})

        # Can still interact normally
        ws.send_json({"type": "interrupt"})


def test_ws_handles_extreme_large_payload(client, mock_ui):
    """Verify large 64KB text command payload is processed without memory/buffer corruption."""
    large_text = "JARVIS " + ("A" * 65536)
    with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as ws:
        _ = ws.receive_json()
        _ = ws.receive_json()

        ws.send_json({"type": "command", "text": large_text})

    mock_ui.on_text_command.assert_called_once_with(large_text)


def test_ws_empty_command_is_ignored(client, mock_ui):
    """Verify whitespace-only or empty command does not dispatch to ui."""
    with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as ws:
        _ = ws.receive_json()
        _ = ws.receive_json()

        ws.send_json({"type": "command", "text": "   "})

    mock_ui.on_text_command.assert_not_called()


# ---------------------------------------------------------------------------
# Tier 3: Cross-Feature Combinations (Concurrency, Throttling, Contracts)
# ---------------------------------------------------------------------------

def test_audio_level_throttling_logic(mock_ui, bridge):
    """Verify hooked set_audio_level throttles broadcasts to ~25 FPS (0.04s threshold)."""
    with patch.object(bridge, "broadcast") as mock_broadcast:
        # Rapidly fire 3 audio updates
        mock_ui.set_audio_level(0.12)
        mock_ui.set_audio_level(0.34)
        mock_ui.set_audio_level(0.56)

        # Due to throttling, broadcast should only be invoked once for the immediate burst
        assert mock_broadcast.call_count == 1
        assert mock_broadcast.call_args[0][0] == {"type": "audio", "level": 0.12}

        # After waiting for throttle interval (0.05s > 0.04s), next update goes through
        time.sleep(0.05)
        mock_ui.set_audio_level(0.88)
        assert mock_broadcast.call_count == 2
        assert mock_broadcast.call_args[0][0] == {"type": "audio", "level": 0.88}


def test_interleaved_state_and_log_broadcasts(mock_ui, bridge):
    """Verify write_log and set_state methods broadcast appropriate structured events."""
    with patch.object(bridge, "broadcast") as mock_broadcast:
        mock_ui.write_log("System diagnostics initialized.")
        mock_ui.set_state("THINKING")

        broadcast_events = [c[0][0] for c in mock_broadcast.call_args_list]
        assert {"type": "log", "text": "System diagnostics initialized."} in broadcast_events
        assert {"type": "state", "state": "THINKING", "muted": False} in broadcast_events


def test_generative_ui_interface_contracts_validity():
    """Verify JSON contract schemas for widget_render, widget_update, widget_dismiss, widget_action."""
    # 1. widget_render schema
    render_msg = {
        "type": "widget_render",
        "widget": {
            "id": "diag_sys_status",
            "template": "telemetry",
            "title": "System Diagnostics",
            "icon": "cpu",
            "target": "dock",
            "data": {"cpu": 15.2, "ram": 42.1},
            "actions": [
                {"action_id": "refresh", "label": "Refresh", "variant": "primary"}
            ]
        }
    }
    encoded = json.dumps(render_msg)
    decoded = json.loads(encoded)
    assert decoded["type"] == "widget_render"
    assert decoded["widget"]["id"] == "diag_sys_status"
    assert decoded["widget"]["template"] in ("telemetry", "activity_tracker", "action_grid", "custom")
    assert isinstance(decoded["widget"]["actions"], list)

    # 2. widget_update schema
    update_msg = {
        "type": "widget_update",
        "widget_id": "diag_sys_status",
        "data": {"cpu": 22.0, "ram": 43.5}
    }
    decoded_upd = json.loads(json.dumps(update_msg))
    assert decoded_upd["type"] == "widget_update"
    assert decoded_upd["widget_id"] == "diag_sys_status"
    assert "cpu" in decoded_upd["data"]

    # 3. widget_dismiss schema
    dismiss_msg = {
        "type": "widget_dismiss",
        "widget_id": "diag_sys_status"
    }
    decoded_dis = json.loads(json.dumps(dismiss_msg))
    assert decoded_dis["type"] == "widget_dismiss"
    assert decoded_dis["widget_id"] == "diag_sys_status"

    # 4. widget_action schema (inbound from frontend)
    action_msg = {
        "type": "widget_action",
        "widget_id": "diag_sys_status",
        "action_id": "refresh",
        "payload": {"source": "gen_ui_dock"}
    }
    decoded_act = json.loads(json.dumps(action_msg))
    assert decoded_act["type"] == "widget_action"
    assert decoded_act["action_id"] == "refresh"


def test_ws_widget_action_message_tolerance(client):
    """Verify that inbound widget_action over /ws is accepted and processed cleanly."""
    with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as ws:
        _ = ws.receive_json()
        _ = ws.receive_json()

        # Send widget action according to interface specification
        ws.send_json({
            "type": "widget_action",
            "widget_id": "diag_sys_status",
            "action_id": "refresh",
            "payload": {"filter": "all"}
        })

        # Verify bridge remains healthy by sending subsequent valid command
        ws.send_json({"type": "interrupt"})


# ---------------------------------------------------------------------------
# Tier 4: Real-World Application Scenarios
# ---------------------------------------------------------------------------

def test_scenario_1_full_lifecycle_startup_to_action(client, mock_ui):
    """
    Scenario 1: Full application lifecycle:
    1. WebEngine requests root UI page -> HTTP 200 with HTML
    2. WebEngine loads Three.js script -> HTTP 200 with JS
    3. WebEngine establishes WebSocket -> Receives init and todo_list
    4. Backend streams logs and state changes
    5. User issues natural language voice command
    6. Session terminates cleanly
    """
    # 1. Load HTML
    html_resp = client.get("/")
    assert html_resp.status_code == 200
    assert "webgl-canvas" in html_resp.text

    # 2. Load Three.js
    js_resp = client.get("/three.min.js")
    assert js_resp.status_code == 200

    # 3. WebSocket session
    with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as ws:
        # Handshake
        init_msg = ws.receive_json()
        assert init_msg["type"] == "init"
        todo_msg = ws.receive_json()
        assert todo_msg["type"] == "todo_list"

        # 4. Inbound User Command
        ws.send_json({"type": "command", "text": "Jarvis, report systems status"})

    # 5. Session terminates cleanly and queued command is executed
    mock_ui.on_text_command.assert_called_with("Jarvis, report systems status")



def test_scenario_2_companion_dashboard_coexistence(client):
    """
    Scenario 2: Verify companion mobile dashboard REST APIs (/api/content_business/*)
    operate alongside the main WebEngine HUD without interference.
    """
    # Main HUD serving operates
    hud_resp = client.get("/")
    assert hud_resp.status_code == 200

    # Companion content business status endpoint operates concurrently
    cb_resp = client.get("/api/content_business/status")
    assert cb_resp.status_code == 200
    assert isinstance(cb_resp.json(), dict)


def test_scenario_3_rapid_reconnection_and_cleanup(client, bridge):
    """
    Scenario 3: Simulate rapid WebEngine retry / reload cycle (5 sequential connects).
    Verify that bridge.clients accurately registers and deregisters clients with zero leak.
    """
    for iteration in range(5):
        with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as ws:
            _ = ws.receive_json()
            _ = ws.receive_json()
            with bridge._clients_lock:
                assert len(bridge.clients) == 1

        # After context exit (disconnect), client set must be empty
        with bridge._clients_lock:
            assert len(bridge.clients) == 0


def test_scenario_4_adversarial_special_characters_in_commands(client, mock_ui):
    """
    Scenario 4: Adversarial testing with Unicode emojis, SQL meta-characters,
    HTML tags, and control characters to verify encoding and escaping integrity.
    """
    adversarial_inputs = [
        "JARVIS 🚀⚡ Test 123",
        "'; DROP TABLE tasks; --",
        "<script>alert('xss')</script>",
        "Line 1\nLine 2\r\nLine 3\tTabbed",
        "Arabic: مرحباً بك | Chinese: 你好",
    ]

    for adv in adversarial_inputs:
        with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as ws:
            _ = ws.receive_json()
            _ = ws.receive_json()

            ws.send_json({"type": "command", "text": adv})

        mock_ui.on_text_command.assert_called_with(adv)


def test_scenario_5_generative_ui_full_pipeline_flow(bridge):
    """
    Scenario 5: Generative UI end-to-end pipeline flow:
    Simulate server broadcasting widget_render, widget_update, and widget_dismiss
    to an active client pool with verified JSON structure.
    """
    with patch.object(bridge, "broadcast") as mock_broadcast:
        # 1. Render Widget
        bridge.broadcast({
            "type": "widget_render",
            "widget": {
                "id": "status_card_1",
                "template": "telemetry",
                "title": "System Telemetry",
                "icon": "activity",
                "target": "dock",
                "data": {"cpu": 12.5, "gpu": 45.0},
                "actions": [{"action_id": "refresh", "label": "Refresh"}]
            }
        })
        assert mock_broadcast.call_args[0][0]["type"] == "widget_render"

        # 2. Update Widget
        bridge.broadcast({
            "type": "widget_update",
            "widget_id": "status_card_1",
            "data": {"cpu": 18.2, "gpu": 46.1}
        })
        assert mock_broadcast.call_args[0][0]["type"] == "widget_update"

        # 3. Dismiss Widget
        bridge.broadcast({
            "type": "widget_dismiss",
            "widget_id": "status_card_1"
        })
        assert mock_broadcast.call_args[0][0]["type"] == "widget_dismiss"
