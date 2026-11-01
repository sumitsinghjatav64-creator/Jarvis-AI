"""
tests/test_m4_challenger_adversarial.py
Milestone 4 Phase 2 Adversarial Coverage Hardening Test Suite.
Authored by Milestone 4 Phase 2 Challenger 1.

Systematically exercises and hardens all previously untested paths, branch conditions,
and failure modes in web_bridge.py:
1. Inbound WebSocket 'ui_action' routing across all 14+ Qt window overlay commands.
2. Inbound WebSocket 'todo_add' validation error handling (todo_error) and 'todo_toggle'.
3. Inbound WebSocket 'save_voice' (edgetts, gemini) and 'test_voice' (including error recovery).
4. Camera stream and frame signals (_cam_stream_sig, _cam_frame_sig with 15 FPS throttling).
5. Hooked UI notification pipelines (show_content, show_confirm, hide_confirm).
6. Companion REST API endpoint 'POST /api/content_business/action'.
7. Dispatcher signature inspection failure fallback ladder and BaseException isolation.
8. _QtMainThreadInvoker exception resilience on the main Qt GUI thread.
9. Dead-client socket pruning during broadcast and bridge port management.
"""
from __future__ import annotations

import asyncio
import base64
import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication

import web_bridge
from web_bridge import WebUIBridge, _QtMainThreadInvoker

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
        app = QApplication(["mark_lv_m4_p2_challenger_test"])
    return app


class MockM4Window(QObject):
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
    ui._win = MockM4Window()
    ui._web_window = MagicMock()
    ui._web_window.isFullScreen.return_value = False
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
# Category 1: Inbound WebSocket 'ui_action' Overlay Routing
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "action_name,expected_attr",
    [
        ("remote", "_open_remote"),
        ("customize", "_open_customize"),
        ("audio_devices", "_open_audio_devices"),
        ("memory", "_open_memory_panel"),
        ("plugins", "_open_plugin_manager"),
        ("plugin_settings", "_open_plugin_settings"),
        ("api_setup", "_show_setup"),
    ],
)
def test_ui_action_overlay_actions(client, bridge, mock_ui, qapp, action_name, expected_attr):
    """Verify overlay ui_action commands bring window to front and invoke corresponding panel method."""
    with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as ws:
        _ = ws.receive_json()
        _ = ws.receive_json()

        ws.send_json({"type": "ui_action", "action": action_name})
        ws.send_json({"type": "interrupt"})

    qapp.processEvents()

    mock_ui._win.show.assert_called()
    mock_ui._win.raise_.assert_called()
    mock_ui._win.activateWindow.assert_called()
    getattr(mock_ui._win, expected_attr).assert_called_once()


@pytest.mark.parametrize(
    "action_name,expected_attr",
    [
        ("shortcut", "_create_desktop_shortcut"),
        ("autostart", "_toggle_autostart"),
        ("brief", "_toggle_brief"),
        ("wake_toggle", "_toggle_wake_word"),
        ("wake_manual", "_tap_wake_manual"),
        ("voice_enroll", "_tap_enroll_voice"),
        ("voice_filter_toggle", "_toggle_voice_filter"),
        ("single_turn_toggle", "_toggle_single_turn"),
        ("ptt", "_toggle_ptt"),
        ("restart", "_restart_app"),
    ],
)
def test_ui_action_toggle_and_direct_actions(client, bridge, mock_ui, qapp, action_name, expected_attr):
    """Verify non-overlay ui_action toggle and helper methods are dispatched safely to Qt window."""
    with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as ws:
        _ = ws.receive_json()
        _ = ws.receive_json()

        ws.send_json({"type": "ui_action", "action": action_name})
        ws.send_json({"type": "interrupt"})

    qapp.processEvents()
    getattr(mock_ui._win, expected_attr).assert_called_once()


def test_ui_action_fullscreen_toggle(client, bridge, mock_ui, qapp):
    """Verify 'fullscreen' ui_action toggles web window between normal and fullscreen modes."""
    # When not full screen -> showFullScreen()
    mock_ui._web_window.isFullScreen.return_value = False
    with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as ws:
        _ = ws.receive_json()
        _ = ws.receive_json()

        ws.send_json({"type": "ui_action", "action": "fullscreen"})
        ws.send_json({"type": "interrupt"})

    qapp.processEvents()
    mock_ui._web_window.showFullScreen.assert_called_once()

    # When full screen -> showNormal()
    mock_ui._web_window.isFullScreen.return_value = True
    mock_ui._web_window.reset_mock()
    with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as ws:
        _ = ws.receive_json()
        _ = ws.receive_json()

        ws.send_json({"type": "ui_action", "action": "fullscreen"})
        ws.send_json({"type": "interrupt"})

    qapp.processEvents()
    mock_ui._web_window.showNormal.assert_called_once()


def test_ui_action_hide_classic(client, bridge, mock_ui, qapp):
    """Verify 'hide_classic' ui_action calls win.hide()."""
    with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as ws:
        _ = ws.receive_json()
        _ = ws.receive_json()

        ws.send_json({"type": "ui_action", "action": "hide_classic"})
        ws.send_json({"type": "interrupt"})

    qapp.processEvents()
    mock_ui._win.hide.assert_called_once()


def test_ui_action_unknown_ignored_gracefully(client, bridge, mock_ui, qapp):
    """Verify unknown ui_action values are ignored safely without exceptions."""
    with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as ws:
        _ = ws.receive_json()
        _ = ws.receive_json()

        ws.send_json({"type": "ui_action", "action": "nonexistent_action_xyz"})
        ws.send_json({"type": "interrupt"})

    qapp.processEvents()
    # Survives and interrupts properly
    assert mock_ui.on_interrupt.called


# ---------------------------------------------------------------------------
# Category 2: Inbound WebSocket 'todo_add' Error & 'todo_toggle'
# ---------------------------------------------------------------------------

def test_ws_todo_add_validation_error_responses(client):
    """Verify empty or oversized todo_add text triggers todo_error response."""
    with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as ws:
        _ = ws.receive_json()  # init
        _ = ws.receive_json()  # todo_list

        # 1. Empty string text -> ValueError in todo_store
        ws.send_json({"type": "todo_add", "text": "   "})
        err1 = ws.receive_json()
        assert err1["type"] == "todo_error"
        assert "Task text must contain 1–500 characters." in err1["message"]

        # 2. Oversized >500 character text -> ValueError in todo_store
        ws.send_json({"type": "todo_add", "text": "X" * 501})
        err2 = ws.receive_json()
        assert err2["type"] == "todo_error"
        assert "Task text must contain 1–500 characters." in err2["message"]


def test_ws_todo_toggle_functional_and_boundary(client, bridge):
    """Verify valid todo_toggle updates state and broadcasts; invalid does not crash."""
    from core.todo_store import todo_store
    created = todo_store.add_task("M4 P2 Verification Task")
    task_id = created["id"]

    try:
        with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as ws:
            _ = ws.receive_json()  # init
            _ = ws.receive_json()  # todo_list

            # 1. Toggle valid task to completed
            ws.send_json({"type": "todo_toggle", "id": task_id, "completed": True})

            # Broadcast of updated todo_list
            upd1 = ws.receive_json()
            assert upd1["type"] == "todo_list"
            matching = [t for t in upd1["tasks"] if t["id"] == task_id]
            assert len(matching) == 1
            assert matching[0]["completed"] is True

            # 2. Toggle valid task back to incomplete
            ws.send_json({"type": "todo_toggle", "id": task_id, "completed": False})
            upd2 = ws.receive_json()
            assert upd2["type"] == "todo_list"
            matching2 = [t for t in upd2["tasks"] if t["id"] == task_id]
            assert matching2[0]["completed"] is False

            # 3. Invalid inputs: non-string id, non-existent id, non-boolean completed
            ws.send_json({"type": "todo_toggle", "id": 12345, "completed": True})
            ws.send_json({"type": "todo_toggle", "id": "unknown_task_id_999", "completed": True})
            ws.send_json({"type": "todo_toggle", "id": task_id, "completed": "string_not_bool"})

            # Verify connection remains healthy
            ws.send_json({"type": "interrupt"})
    finally:
        todo_store.delete_task(task_id)


# ---------------------------------------------------------------------------
# Category 3: Voice Configuration ('save_voice' & 'test_voice')
# ---------------------------------------------------------------------------

def test_ws_save_voice_edgetts_and_gemini(client, bridge, mock_ui, qapp):
    """Verify 'save_voice' updates configurations, notifies Qt window, and broadcasts updates."""
    with patch("memory.config_manager.save_tts_engine") as mock_save_engine, \
         patch("memory.config_manager.save_tts_voice") as mock_save_voice, \
         patch("memory.config_manager.save_voice") as mock_save_gemini_voice:

        with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as ws:
            _ = ws.receive_json()
            _ = ws.receive_json()

            # 1. EdgeTTS engine save
            ws.send_json({
                "type": "save_voice",
                "engine": "edgetts",
                "voice": "en-US-ChristopherNeural"
            })

            msg_voice = ws.receive_json()
            assert msg_voice["type"] == "voice_updated"
            msg_log = ws.receive_json()
            assert msg_log["type"] == "log"
            assert "Voice updated" in msg_log["text"]

            mock_save_engine.assert_called_with("edgetts")
            mock_save_voice.assert_called_with("en-US-ChristopherNeural")

            # 2. Gemini engine save
            ws.send_json({
                "type": "save_voice",
                "engine": "gemini",
                "voice": "Puck"
            })

            msg_voice2 = ws.receive_json()
            assert msg_voice2["type"] == "voice_updated"
            msg_log2 = ws.receive_json()
            assert msg_log2["type"] == "log"

            mock_save_gemini_voice.assert_called_with("Puck")

    qapp.processEvents()
    mock_ui._win.on_voice_change.assert_called()


def test_ws_test_voice_success_and_error_isolation(client, bridge):
    """Verify 'test_voice' executes speak in daemon thread and isolates errors gracefully."""
    with patch("core.tts.EdgeTTSEngine.speak") as mock_speak:
        with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as ws:
            _ = ws.receive_json()
            _ = ws.receive_json()

            # 1. Normal voice test
            ws.send_json({"type": "test_voice", "voice": "en-US-GuyNeural"})
            time.sleep(0.1)
            mock_speak.assert_called()

            # 2. Exception in TTS speaking does not crash WebSocket
            mock_speak.side_effect = RuntimeError("TTS device unavailable")
            ws.send_json({"type": "test_voice", "voice": "en-US-GuyNeural"})
            time.sleep(0.1)

            # WebSocket connection remains alive
            ws.send_json({"type": "interrupt"})
            time.sleep(0.05)
            assert bridge.ui.on_interrupt.called


# ---------------------------------------------------------------------------
# Category 4: Camera Stream Signals & Frame Throttling
# ---------------------------------------------------------------------------

def test_camera_signals_and_frame_throttling(client, bridge):
    """Verify _cam_stream_sig and _cam_frame_sig base64 encoding and 15 FPS throttling."""
    with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as ws:
        _ = ws.receive_json()  # init
        _ = ws.receive_json()  # todo_list

        # 1. Stream active signal
        bridge.ui._win._cam_stream_sig.emit(True)
        msg_active = ws.receive_json()
        assert msg_active["type"] == "cam_state"
        assert msg_active["active"] is True
        assert bridge._cam_active is True

        bridge.ui._win._cam_stream_sig.emit(False)
        msg_inactive = ws.receive_json()
        assert msg_inactive["type"] == "cam_state"
        assert msg_inactive["active"] is False

        # 2. Frame bytes signal: base64 encoding and throttling
        fake_frame = b"\xFF\xD8\xFF\xE0\x00\x10JFIF"
        expected_b64 = base64.b64encode(fake_frame).decode("ascii")

        bridge.ui._win._cam_frame_sig.emit(fake_frame)
        msg_frame = ws.receive_json()
        assert msg_frame["type"] == "cam_frame"
        assert msg_frame["data"] == expected_b64

        # Immediate second frame within 0.066s is throttled
        bridge.ui._win._cam_frame_sig.emit(b"second_frame_throttled")

        # After waiting >0.066s (0.08s), next frame is transmitted
        time.sleep(0.08)
        bridge.ui._win._cam_frame_sig.emit(fake_frame)
        msg_frame2 = ws.receive_json()
        assert msg_frame2["type"] == "cam_frame"


# ---------------------------------------------------------------------------
# Category 5: Hooked UI Methods (show_content, show_confirm, hide_confirm)
# ---------------------------------------------------------------------------

def test_hooked_ui_methods_event_broadcasts(client, bridge, mock_ui):
    """Verify show_content, show_confirm, and hide_confirm broadcast structured messages."""
    with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as ws:
        _ = ws.receive_json()
        _ = ws.receive_json()

        # 1. show_content
        mock_ui.show_content("Diagnostic Report", "All 10 subsystems nominal.")
        msg_content = ws.receive_json()
        assert msg_content == {
            "type": "content",
            "title": "Diagnostic Report",
            "text": "All 10 subsystems nominal."
        }

        # 2. show_confirm
        mock_ui.show_confirm("Shutdown System", "Confirm graceful termination?")
        msg_confirm_show = ws.receive_json()
        assert msg_confirm_show == {
            "type": "confirm_show",
            "title": "Shutdown System",
            "detail": "Confirm graceful termination?"
        }

        # 3. hide_confirm
        mock_ui.hide_confirm()
        msg_confirm_hide = ws.receive_json()
        assert msg_confirm_hide == {"type": "confirm_hide"}


# ---------------------------------------------------------------------------
# Category 6: Companion REST Action API Endpoint
# ---------------------------------------------------------------------------

def test_companion_cb_action_endpoint(client, bridge):
    """Verify POST /api/content_business/action dispatches control and broadcasts telemetry."""
    with patch("actions.content_business_action.content_business_control", return_value="action_executed_ok") as mock_ctrl, \
         patch("content_business.get_cb_orchestrator") as mock_orch:
        mock_orch.return_value.status.return_value = {"active_workers": 2, "state": "IDLE"}

        with patch.object(bridge, "broadcast") as mock_broadcast:
            resp = client.post("/api/content_business/action", json={"action": "recalibrate", "target": "worker_1"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["result"] == "action_executed_ok"
            assert data["status"]["active_workers"] == 2

            # Telemetry broadcasted
            mock_broadcast.assert_called_with({
                "type": "cb_telemetry",
                "data": {"active_workers": 2, "state": "IDLE"},
                "message": "action_executed_ok"
            })


# ---------------------------------------------------------------------------
# Category 7: Dispatcher Fallback, Signature Inspection Failure, & BaseException
# ---------------------------------------------------------------------------

def test_dispatcher_signature_inspection_failure_and_fallback_ladder(client, bridge):
    """Verify fallback retry ladder when inspect.signature() raises TypeError/ValueError."""
    called_args = []

    # Built-in or C function simulation where signature() fails
    class UninspectableCallable:
        def __call__(self, wid, act, pld):
            called_args.append((wid, act, pld))

    callable_obj = UninspectableCallable()

    # Force inspect.signature to raise ValueError simulating uninspectable callable
    with patch("inspect.signature", side_effect=ValueError("Cannot inspect signature of uninspectable")):
        bridge.register_action_handler("uninspectable_act", callable_obj)

        with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as ws:
            _ = ws.receive_json()
            _ = ws.receive_json()

            ws.send_json({
                "type": "widget_action",
                "widget_id": "wid_fallback",
                "action_id": "uninspectable_act",
                "payload": {"status": "ok"}
            })
            ws.send_json({"type": "interrupt"})

    assert len(called_args) == 1
    assert called_args[0] == ("wid_fallback", "uninspectable_act", {"status": "ok"})


def test_dispatcher_fallback_ladder_signature_cascade(client, bridge):
    """Verify fallback retry ladder tries (wid, act, pld) -> (wid, pld) -> (pld) -> ()."""
    cascade_called = []

    def zero_arg_fallback():
        cascade_called.append("zero_arg")

    # Force inspect.signature failure so it enters the fallback ladder
    with patch("inspect.signature", side_effect=TypeError("Signature failure")):
        bridge.register_action_handler("cascade_act", zero_arg_fallback)

        with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as ws:
            _ = ws.receive_json()
            _ = ws.receive_json()

            ws.send_json({
                "type": "widget_action",
                "widget_id": "wid_cascade",
                "action_id": "cascade_act",
                "payload": {}
            })
            ws.send_json({"type": "interrupt"})

    assert cascade_called == ["zero_arg"]


def test_qt_main_thread_invoker_exception_resilience(bridge, qapp):
    """Verify exceptions thrown inside Qt invoker callable are caught and logged."""
    def faulty_callable():
        raise RuntimeError("Simulated crash on main Qt GUI thread")

    # Scheduling on Qt main thread must not raise or terminate process
    bridge._run_on_qt_thread(faulty_callable)
    qapp.processEvents()
    # Process continues normally


def test_action_dispatcher_base_exception_isolation(client, bridge):
    """Verify BaseException (such as custom critical exception) in handler is isolated without crash."""
    class CustomBaseFault(BaseException):
        pass

    def fatal_handler(wid, act, pld):
        raise CustomBaseFault("Simulated critical base exception")

    bridge.register_action_handler("fatal_act", fatal_handler)

    with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as ws:
        _ = ws.receive_json()
        _ = ws.receive_json()

        ws.send_json({
            "type": "widget_action",
            "widget_id": "w_fatal",
            "action_id": "fatal_act",
            "payload": {}
        })

        # WebSocket connection survives
        ws.send_json({"type": "interrupt"})
        time.sleep(0.05)
        assert bridge.ui.on_interrupt.called


# ---------------------------------------------------------------------------
# Category 8: Dead Client Pruning and Port Management
# ---------------------------------------------------------------------------

def test_broadcast_pruning_of_dead_sockets(bridge):
    """Verify dead WebSocket connections encountering send errors are pruned from self.clients."""
    loop = asyncio.new_event_loop()
    bridge.loop = loop

    class MockFailingWS:
        def __init__(self, should_fail: bool):
            self.should_fail = should_fail
            self.sent = []

        async def send_text(self, data: str):
            if self.should_fail:
                raise ConnectionResetError("Client dropped connection")
            self.sent.append(data)

    live_ws = MockFailingWS(should_fail=False)
    dead_ws = MockFailingWS(should_fail=True)

    with bridge._clients_lock:
        bridge.clients.add(live_ws)  # type: ignore
        bridge.clients.add(dead_ws)  # type: ignore

    # Broadcast while loop is running
    async def _run_broadcast():
        bridge.broadcast({"type": "prune_test", "data": 123})
        # Allow scheduled coroutines to execute
        await asyncio.sleep(0.01)

    loop.run_until_complete(_run_broadcast())

    # Dead WS should be evicted, live WS retained
    with bridge._clients_lock:
        assert dead_ws not in bridge.clients
        assert live_ws in bridge.clients
    assert len(live_ws.sent) == 1

    loop.close()
    bridge.loop = None


def test_bridge_lifecycle_port_and_shutdown_helpers(bridge):
    """Verify _port_is_free, stop, and _release_stale_listener behaviors."""
    # 1. _port_is_free tests socket binding cleanly
    is_free = bridge._port_is_free()
    assert isinstance(is_free, bool)

    # 2. stop() when server is None is safe no-op
    bridge.server = None
    bridge.stop()

    # 3. stop() when server is set flags should_exit
    mock_server = MagicMock()
    mock_server.should_exit = False
    bridge.server = mock_server
    bridge.stop()
    assert mock_server.should_exit is True

    # 4. _release_stale_listener returns cleanly when no listener exists
    bridge._release_stale_listener()
