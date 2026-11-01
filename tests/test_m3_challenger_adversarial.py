"""
tests/test_m3_challenger_adversarial.py
Adversarial and boundary stress tests authored by M3 Challenger 2.
Empirically tests malformed WebSocket payloads, outbound dispatch edge cases,
variable callback signatures, circular references, and action handler exception isolation.
"""
from __future__ import annotations

import json
import time
from typing import Any
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient
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
        app = QApplication(["mark_lv_m3_challenger_test"])
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
    ui.hide_confirm = MagicMock()
    ui.on_text_command = MagicMock()
    ui.on_interrupt = MagicMock()
    ui.start_camera_stream = MagicMock()
    ui.stop_camera_stream = MagicMock()
    return ui


@pytest.fixture
def bridge(mock_ui):
    return WebUIBridge(mock_ui, host="127.0.0.1", port=8765)


@pytest.fixture
def client(bridge):
    return TestClient(bridge.app, base_url="http://127.0.0.1:8765")


# ---------------------------------------------------------------------------
# Test Category 1: Malformed WebSocket Messages
# ---------------------------------------------------------------------------

def test_malformed_ws_non_dict_messages(client, bridge):
    """Verify non-dict JSON messages (scalars, lists, nulls) are safely dropped without crashing WS."""
    with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as ws:
        _ = ws.receive_json()  # init
        _ = ws.receive_json()  # todo_list

        adversarial_raw = [
            json.dumps("plain string message"),
            json.dumps(12345),
            json.dumps(3.14159),
            json.dumps(True),
            json.dumps(False),
            json.dumps(None),
            json.dumps([1, 2, 3]),
            json.dumps([{"nested": "array"}]),
        ]

        for payload in adversarial_raw:
            ws.send_text(payload)

        # Confirm connection remains healthy and responsive
        ws.send_json({"type": "interrupt"})
        time.sleep(0.1)
        assert bridge.ui.on_interrupt.called


def test_malformed_ws_truncated_and_corrupt_json(client, bridge):
    """Verify corrupted, truncated, and non-JSON text payloads are handled gracefully."""
    with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as ws:
        _ = ws.receive_json()  # init
        _ = ws.receive_json()  # todo_list

        corrupt_payloads = [
            "",
            "   ",
            "\n\t",
            "not a json at all",
            '{"type": "widget_action",',
            '{"type": "widget_action", "widget_id":',
            '{"key": "value"',
            "{unquoted_key: 123}",
            '{"truncated_string": "abc',
            "nul",
            "undefined",
            "NaN",
            "\x00\x01\x02\x03",
        ]

        for corrupt in corrupt_payloads:
            ws.send_text(corrupt)

        # Connection should stay open and process subsequent valid messages
        import time
        ws.send_json({"type": "interrupt"})
        time.sleep(0.1)
        assert bridge.ui.on_interrupt.called


def test_malformed_ws_missing_fields_and_unusual_types(client, bridge):
    """Verify missing, empty, or unexpected field types in widget_action messages are handled safely."""
    received = []
    bridge.register_action_handler("test_act", lambda wid, act, pld: received.append((wid, act, pld)))

    with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as ws:
        _ = ws.receive_json()  # init
        _ = ws.receive_json()  # todo_list

        malformed_actions = [
            {"type": "widget_action"},  # missing both
            {"type": "widget_action", "action_id": "test_act"},  # missing widget_id
            {"type": "widget_action", "widget_id": "w1"},  # missing action_id
            {"type": "widget_action", "widget_id": "", "action_id": "test_act"},  # empty widget_id
            {"type": "widget_action", "widget_id": "w1", "action_id": ""},  # empty action_id
            {"type": "widget_action", "widget_id": "   ", "action_id": "test_act"},  # whitespace widget_id
            {"type": "widget_action", "widget_id": None, "action_id": "test_act"},  # null widget_id
            {"type": "widget_action", "widget_id": "w1", "action_id": None},  # null action_id
            {"type": "widget_action", "widget_id": False, "action_id": "test_act"},  # bool widget_id
            {"type": "widget_action", "widget_id": 0, "action_id": "test_act"},  # 0 widget_id
            {"type": "widget_action", "widget_id": "w1", "action_id": 0},  # 0 action_id
        ]

        for msg in malformed_actions:
            ws.send_json(msg)

        assert len(received) == 0

        # Now test non-dict payloads: should be sanitized to empty dict {}
        ws.send_json({"type": "widget_action", "widget_id": "w_ok", "action_id": "test_act", "payload": None})
        ws.send_json({"type": "widget_action", "widget_id": "w_ok", "action_id": "test_act", "payload": "string_payload"})
        ws.send_json({"type": "widget_action", "widget_id": "w_ok", "action_id": "test_act", "payload": 12345})
        ws.send_json({"type": "widget_action", "widget_id": "w_ok", "action_id": "test_act", "payload": [1, 2, 3]})
        ws.send_json({"type": "widget_action", "widget_id": "w_ok", "action_id": "test_act", "payload": True})

        ws.send_json({"type": "interrupt"})

    assert len(received) == 5
    for item in received:
        assert item == ("w_ok", "test_act", {})


# ---------------------------------------------------------------------------
# Test Category 2: Outbound Dispatch Helpers Boundary Mutations
# ---------------------------------------------------------------------------

def test_outbound_helpers_invalid_inputs(bridge):
    """Verify render_widget, update_widget, dismiss_widget, clear_all_widgets input rejection."""
    # render_widget
    assert bridge.render_widget(None) is False
    assert bridge.render_widget("string") is False
    assert bridge.render_widget(123) is False
    assert bridge.render_widget([{"id": "w1"}]) is False
    assert bridge.render_widget(True) is False

    # render_widget with empty dict -> auto-generates ID and target
    assert bridge.render_widget({}) is True
    with bridge._widgets_lock:
        assert len(bridge._active_widgets) == 1
        wid = list(bridge._active_widgets.keys())[0]
        assert wid.startswith("widget_")
        assert bridge._active_widgets[wid]["target"] == "dock"

    # update_widget invalid widget_id
    assert bridge.update_widget("", {"key": "val"}) is False
    assert bridge.update_widget("   ", {"key": "val"}) is False
    assert bridge.update_widget(None, {"key": "val"}) is False
    assert bridge.update_widget(123, {"key": "val"}) is False
    assert bridge.update_widget([], {"key": "val"}) is False

    # update_widget invalid data
    assert bridge.update_widget("w1", None) is False
    assert bridge.update_widget("w1", "not_a_dict") is False
    assert bridge.update_widget("w1", 1234) is False
    assert bridge.update_widget("w1", [1, 2]) is False

    # dismiss_widget invalid widget_id
    assert bridge.dismiss_widget("") is False
    assert bridge.dismiss_widget("   ") is False
    assert bridge.dismiss_widget(None) is False
    assert bridge.dismiss_widget(12345) is False
    assert bridge.dismiss_widget({"id": "w1"}) is False

    # clear_all_widgets with unexpected options
    assert bridge.clear_all_widgets(options={"unknown_key": "val", "nested": {"a": 1}}) is True
    assert bridge.clear_all_widgets(options="not_a_dict") is True
    assert bridge.clear_all_widgets(target=1234) is True  # non-string target falls back to None


def test_cyclic_references_in_payloads(client, bridge):
    """Verify cyclic data structures in payloads are handled safely without crashing broadcast."""
    cyclic_dict: dict[str, Any] = {"title": "Cyclic Widget"}
    cyclic_dict["self"] = cyclic_dict

    with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as ws:
        _ = ws.receive_json()
        _ = ws.receive_json()

        # broadcast() with cyclic payload must not crash process
        bridge.broadcast({"type": "custom_cyclic", "data": cyclic_dict})

        # render_widget() with cyclic payload
        # Note: copy.deepcopy(cyclic_dict) succeeds because deepcopy handles cycles with memo dict
        ok = bridge.render_widget(cyclic_dict)
        assert ok is True

        # Ensure WS connection is still healthy
        ws.send_json({"type": "interrupt"})
        time.sleep(0.1)
        assert bridge.ui.on_interrupt.called


# ---------------------------------------------------------------------------
# Test Category 3: Variable Callback Signatures
# ---------------------------------------------------------------------------

def test_variable_callback_signatures(client, bridge):
    """Verify action dispatcher correctly handles all variable callback signatures."""
    results = {}

    def cb_zero():
        results["zero"] = True

    def cb_one(payload):
        results["one"] = payload

    def cb_two(widget_id, payload):
        results["two"] = (widget_id, payload)

    def cb_three(widget_id, action_id, payload):
        results["three"] = (widget_id, action_id, payload)

    def cb_varargs(*args, **kwargs):
        results["varargs"] = (args, kwargs)

    class CallableObj:
        def __call__(self, wid, act, pld):
            results["callable_obj"] = (wid, act, pld)

    bridge.register_action_handler("act_0", cb_zero)
    bridge.register_action_handler("act_1", cb_one)
    bridge.register_action_handler("act_2", cb_two)
    bridge.register_action_handler("act_3", cb_three)
    bridge.register_action_handler("act_var", cb_varargs)
    bridge.register_action_handler("act_obj", CallableObj())

    with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as ws:
        _ = ws.receive_json()
        _ = ws.receive_json()

        ws.send_json({"type": "widget_action", "widget_id": "w0", "action_id": "act_0", "payload": {"k": 0}})
        ws.send_json({"type": "widget_action", "widget_id": "w1", "action_id": "act_1", "payload": {"k": 1}})
        ws.send_json({"type": "widget_action", "widget_id": "w2", "action_id": "act_2", "payload": {"k": 2}})
        ws.send_json({"type": "widget_action", "widget_id": "w3", "action_id": "act_3", "payload": {"k": 3}})
        ws.send_json({"type": "widget_action", "widget_id": "w_var", "action_id": "act_var", "payload": {"k": 4}})
        ws.send_json({"type": "widget_action", "widget_id": "w_obj", "action_id": "act_obj", "payload": {"k": 5}})
        ws.send_json({"type": "interrupt"})

    assert results["zero"] is True
    assert results["one"] == {"k": 1}
    assert results["two"] == ("w2", {"k": 2})
    assert results["three"] == ("w3", "act_3", {"k": 3})
    assert results["varargs"][0] == ("w_var", "act_var", {"k": 4})
    assert results["callable_obj"] == ("w_obj", "act_obj", {"k": 5})


# ---------------------------------------------------------------------------
# Test Category 4: Action Handler Exception Isolation Stress Tests
# ---------------------------------------------------------------------------

def test_action_handler_failure_zero_division(client, bridge):
    """Verify handler raising ZeroDivisionError is caught and logged without crashing WebSocket."""
    def div_zero_handler(wid, act, pld):
        _ = 1 / 0

    bridge.register_action_handler("div_zero", div_zero_handler)

    with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as ws:
        _ = ws.receive_json()
        _ = ws.receive_json()

        ws.send_json({"type": "widget_action", "widget_id": "w_err", "action_id": "div_zero", "payload": {}})

        # Verify WebSocket remains open and operational
        ws.send_json({"type": "interrupt"})
        time.sleep(0.1)
        assert bridge.ui.on_interrupt.called


def test_action_handler_failure_value_error_isolation(client, bridge):
    """
    CRITICAL ADVERSARIAL TEST:
    Verify whether an action handler raising ValueError crashes the WebSocket connection.
    In flawed implementations, except (ValueError, TypeError) re-invokes the handler,
    causing ValueError to escape uncaught and terminate the WebSocket connection loop.
    """
    def value_error_handler(wid, act, pld):
        raise ValueError("Simulated handler validation error")

    bridge.register_action_handler("val_err", value_error_handler)

    with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as ws:
        _ = ws.receive_json()
        _ = ws.receive_json()

        ws.send_json({"type": "widget_action", "widget_id": "w_err", "action_id": "val_err", "payload": {}})

        # If ValueError escaped, the WebSocket loop crashed and exited, making the connection dead.
        # Sending a message and expecting subsequent operation will fail if the server loop crashed.
        ws.send_json({"type": "interrupt"})
        time.sleep(0.1)
        assert bridge.ui.on_interrupt.called, "WebSocket loop crashed due to handler ValueError!"


def test_action_handler_failure_type_error_isolation(client, bridge):
    """
    CRITICAL ADVERSARIAL TEST:
    Verify whether an action handler raising TypeError (e.g. data type mismatch inside callback)
    crashes the WebSocket connection.
    """
    def type_error_handler(payload):
        # Callback expects int, but receives None or string, raising TypeError internally
        return payload.get("count") + 10

    bridge.register_action_handler("type_err", type_error_handler)

    with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as ws:
        _ = ws.receive_json()
        _ = ws.receive_json()

        ws.send_json({"type": "widget_action", "widget_id": "w_err", "action_id": "type_err", "payload": {"count": None}})

        # WebSocket must survive
        ws.send_json({"type": "interrupt"})
        time.sleep(0.1)
        assert bridge.ui.on_interrupt.called, "WebSocket loop crashed due to handler TypeError!"
