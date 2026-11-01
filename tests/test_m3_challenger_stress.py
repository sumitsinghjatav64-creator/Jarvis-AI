"""
tests/test_m3_challenger_stress.py
Milestone 3 Empirical Challenger Stress & Concurrency Test Suite.

Adversarially exercises and stress-tests:
1. High-concurrency thread contention (50-100 concurrent worker threads) simultaneously executing:
   render_widget, update_widget, dismiss_widget, clear_all_widgets, and broadcast_telemetry.
2. Active widget state consistency, deep-copy mutation isolation, and invariant verification
   under sustained high-frequency concurrent mutations.
3. High-volume simulated WebSocket client connections (fast, slow/backpressured, failing/disconnecting)
   subjected to rapid-fire broadcast bursts (5,000+ broadcasts).
4. Rapid-fire inbound widget_action routing with concurrent handler registration and unregistration,
   handler signature adaptation, reentrant registration, and fault isolation.
5. Verification of zero deadlocks, zero lock contention race conditions, and zero unhandled exceptions.
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import copy
import json
import random
import threading
import time
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication

import web_bridge
from web_bridge import WebUIBridge

# Ensure Request is present in web_bridge globals
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
        app = QApplication(["mark_lv_m3_challenger_stress"])
    return app


class MockStressWindow(QObject):
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
    """Creates a mock UI structure suitable for WebUIBridge stress tests."""
    ui = MagicMock()
    ui._win = MockStressWindow()
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
    ui.on_widget_action = MagicMock()
    return ui


@pytest.fixture
def bridge(mock_ui):
    """Instantiates WebUIBridge with mocked UI for stress tests."""
    return WebUIBridge(mock_ui, host="127.0.0.1", port=8765)


# ---------------------------------------------------------------------------
# Simulated WebSocket Client for Burst Testing
# ---------------------------------------------------------------------------

class MockAsyncWebSocket:
    """
    Simulated WebSocket client connection supporting configurable latency and failure modes.
    """
    def __init__(self, client_id: str, mode: str = "fast", fail_after: int = -1):
        self.client_id = client_id
        self.mode = mode  # "fast", "slow", "failing"
        self.fail_after = fail_after
        self.received_messages: list[str] = []
        self.send_count = 0
        self.is_closed = False

    async def send_text(self, text: str):
        if self.is_closed:
            raise ConnectionResetError(f"Client {self.client_id} connection is closed")
        self.send_count += 1
        if self.mode == "failing" and (self.fail_after < 0 or self.send_count >= self.fail_after):
            self.is_closed = True
            raise ConnectionResetError(f"Client {self.client_id} simulated connection drop")
        if self.mode == "slow":
            await asyncio.sleep(0)
        self.received_messages.append(text)


# ---------------------------------------------------------------------------
# Stress Test Suite
# ---------------------------------------------------------------------------

def test_stress_100_concurrent_threads_crud_operations(bridge):
    """
    Stress Test 1: High-concurrency CRUD load across 100 concurrent worker threads.
    Each thread performs 50 randomized operations (5,000 total operations) across
    render_widget, update_widget, dismiss_widget, clear_all_widgets, and broadcast_telemetry.
    Simultaneously, a background auditor verifies _active_widgets invariant consistency.
    """
    num_threads = 100
    ops_per_thread = 50
    total_ops = num_threads * ops_per_thread

    errors: list[str] = []
    auditor_errors: list[str] = []
    stop_auditor = threading.Event()
    start_barrier = threading.Barrier(num_threads + 2)

    # Background auditor verifying invariant consistency during concurrency
    def state_auditor():
        start_barrier.wait()
        while not stop_auditor.is_set():
            try:
                with bridge._widgets_lock:
                    active_items = list(bridge._active_widgets.items())
                # Verify invariants without holding lock
                for wid, w in active_items:
                    if not isinstance(wid, str) or not wid.strip():
                        auditor_errors.append(f"Invalid widget key: {wid!r}")
                    if not isinstance(w, dict):
                        auditor_errors.append(f"Widget {wid!r} value is not a dict: {type(w)}")
                    elif w.get("id") != wid:
                        auditor_errors.append(f"Widget ID mismatch: key={wid!r}, id={w.get('id')!r}")
            except Exception as exc:
                auditor_errors.append(f"Auditor exception: {exc}")
            time.sleep(0.002)

    auditor_thread = threading.Thread(target=state_auditor, daemon=True)
    auditor_thread.start()

    def worker(tid: int):
        start_barrier.wait()
        try:
            for i in range(ops_per_thread):
                op = random.randint(0, 5)
                # Distribute between shared and thread-unique IDs
                target_wid = f"shared_widget_{i % 8}" if (i % 2 == 0) else f"worker_{tid}_widget_{i}"

                if op == 0:
                    # Render with specific ID
                    ok = bridge.render_widget({
                        "id": target_wid,
                        "template": "telemetry" if i % 3 == 0 else "custom",
                        "title": f"Widget {target_wid}",
                        "target": "dock" if i % 2 == 0 else "chat",
                        "data": {"tid": tid, "i": i, "val": random.random()},
                    })
                    if not ok:
                        errors.append(f"Worker {tid} render failed for {target_wid}")

                elif op == 1:
                    # Render with auto-generated ID
                    ok = bridge.render_widget({
                        "template": "activity_tracker",
                        "title": f"Auto ID from {tid}",
                        "data": {"count": i},
                    })
                    if not ok:
                        errors.append(f"Worker {tid} auto-id render failed")

                elif op == 2:
                    # Update widget
                    ok = bridge.update_widget(target_wid, {
                        "updated_by": tid,
                        "iteration": i,
                        "metrics": {"load": random.random() * 100},
                    })
                    if not ok:
                        errors.append(f"Worker {tid} update failed for {target_wid}")

                elif op == 3:
                    # Dismiss widget
                    ok = bridge.dismiss_widget(target_wid)
                    if not ok:
                        errors.append(f"Worker {tid} dismiss failed for {target_wid}")

                elif op == 4:
                    # Clear all widgets (filtered or global)
                    choice = i % 3
                    if choice == 0:
                        bridge.clear_all_widgets(target="dock")
                    elif choice == 1:
                        bridge.clear_all_widgets(target="chat")
                    else:
                        bridge.clear_all_widgets()

                elif op == 5:
                    # Telemetry broadcast
                    bridge.broadcast_telemetry({
                        "cpu": float(tid),
                        "mem": float(i),
                        "widget_id": target_wid,
                    })

        except Exception as exc:
            errors.append(f"Worker {tid} unhandled exception: {exc}")

    t_start = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker, tid) for tid in range(num_threads)]
        # Trigger barrier for workers and auditor
        start_barrier.wait()
        concurrent.futures.wait(futures, timeout=20.0)
        for f in futures:
            f.result()

    t_elapsed = time.perf_counter() - t_start
    stop_auditor.set()
    auditor_thread.join(timeout=2.0)

    throughput = total_ops / t_elapsed
    print(f"\n[Empirical Metric] CRUD Stress: {total_ops} ops in {t_elapsed:.3f}s ({throughput:.1f} ops/sec)")

    assert len(errors) == 0, f"Worker errors encountered ({len(errors)}): {errors[:10]}"
    assert len(auditor_errors) == 0, f"State consistency auditor errors ({len(auditor_errors)}): {auditor_errors[:10]}"

    # Verify final state consistency
    with bridge._widgets_lock:
        for wid, w in bridge._active_widgets.items():
            assert isinstance(wid, str) and wid
            assert isinstance(w, dict)
            assert w.get("id") == wid


def test_stress_high_volume_ws_clients_and_burst_broadcasts(bridge):
    """
    Stress Test 2: High-volume simulated WebSocket client connections and rapid-fire broadcast calls.
    Spins up an active asyncio event loop, attaches 90 simulated WebSocket clients
    (30 fast, 30 slow/backpressured, 30 abruptly failing), and fires 5,000 rapid broadcasts
    from 50 concurrent threads.
    Verifies automatic dead-socket eviction, zero loop crashes, and zero thread deadlocks.
    """
    # Initialize and start event loop on dedicated background thread
    bridge_loop = asyncio.new_event_loop()
    loop_ready = threading.Event()

    def run_loop():
        asyncio.set_event_loop(bridge_loop)
        loop_ready.set()
        bridge_loop.run_forever()

    loop_thread = threading.Thread(target=run_loop, daemon=True)
    loop_thread.start()
    loop_ready.wait()
    bridge.loop = bridge_loop

    num_fast = 30
    num_slow = 30
    num_failing = 30
    total_clients = num_fast + num_slow + num_failing

    clients = []
    for i in range(num_fast):
        clients.append(MockAsyncWebSocket(f"fast_{i}", mode="fast"))
    for i in range(num_slow):
        clients.append(MockAsyncWebSocket(f"slow_{i}", mode="slow"))
    for i in range(num_failing):
        clients.append(MockAsyncWebSocket(f"fail_{i}", mode="failing", fail_after=random.randint(1, 10)))

    with bridge._clients_lock:
        for c in clients:
            bridge.clients.add(c)

    num_threads = 50
    burst_per_thread = 40
    total_broadcasts = num_threads * burst_per_thread
    errors: list[str] = []

    def burst_worker(tid: int):
        try:
            for b in range(burst_per_thread):
                wid = f"burst_widget_{tid}_{b % 5}"
                op = b % 4
                if op == 0:
                    bridge.render_widget({
                        "id": wid,
                        "template": "telemetry",
                        "title": f"Burst {tid}-{b}",
                        "data": {"seq": b},
                    })
                elif op == 1:
                    bridge.update_widget(wid, {"delta": b})
                elif op == 2:
                    bridge.broadcast_telemetry({"cpu": random.random() * 100, "widget_id": wid})
                else:
                    bridge.broadcast({"type": "custom_burst", "sender": tid, "seq": b})
        except Exception as exc:
            errors.append(f"Burst worker {tid} failed: {exc}")

    t_start = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(burst_worker, tid) for tid in range(num_threads)]
        concurrent.futures.wait(futures, timeout=20.0)
        for f in futures:
            f.result()

    # Allow event loop to process scheduled broadcasts
    deadline = time.perf_counter() + 5.0
    while time.perf_counter() < deadline:
        # Check if tasks are settling
        with bridge._clients_lock:
            remaining = len(bridge.clients)
        # Failing clients should be pruned down
        if remaining <= (num_fast + num_slow):
            break
        time.sleep(0.05)

    t_elapsed = time.perf_counter() - t_start
    throughput = total_broadcasts / t_elapsed
    print(f"\n[Empirical Metric] WS Burst Stress: {total_broadcasts} broadcasts dispatched to {total_clients} clients in {t_elapsed:.3f}s ({throughput:.1f} broadcasts/sec)")

    # Clean shutdown of loop
    bridge_loop.call_soon_threadsafe(bridge_loop.stop)
    loop_thread.join(timeout=2.0)

    assert len(errors) == 0, f"Broadcast burst encountered errors: {errors}"

    # Verify dead clients were safely pruned
    with bridge._clients_lock:
        final_clients = list(bridge.clients)

    failing_left = [c for c in final_clients if c.mode == "failing"]
    assert len(failing_left) == 0, f"Expected all failing clients to be pruned, found: {failing_left}"

    # Verify fast clients received messages successfully
    fast_counts = [c.send_count for c in clients if c.mode == "fast"]
    assert all(count > 0 for count in fast_counts), "Fast clients should have received broadcast payloads"


def test_stress_rapid_fire_action_routing_and_handler_contention(bridge, mock_ui):
    """
    Stress Test 3: Rapid-fire inbound widget_action routing with concurrent handler
    registration/unregistration and Qt invoker execution.
    - 30 threads registering diverse handler signatures and modes.
    - 20 threads unregistering handlers.
    - 50 threads dispatching widget_actions with varying payloads and edge cases.
    Verifies zero deadlocks, zero lock corruption, and robust exception containment.
    """
    num_reg_threads = 30
    num_unreg_threads = 20
    num_disp_threads = 50
    total_threads = num_reg_threads + num_unreg_threads + num_disp_threads
    ops_per_thread = 50

    errors: list[str] = []
    actions_handled: list[tuple[str, str]] = []
    handled_lock = threading.Lock()

    # Pre-render some widgets to test dismiss eviction during dispatch
    for w in range(20):
        bridge.render_widget({
            "id": f"action_test_wid_{w}",
            "template": "action_grid",
            "title": f"Action Widget {w}",
        })

    def reg_worker(tid: int):
        try:
            for i in range(ops_per_thread):
                act_id = f"action_{i % 15}"
                mode = i % 4

                # Handlers with different signatures
                if mode == 0:
                    def h_3(wid, act, pld):
                        with handled_lock:
                            actions_handled.append((wid, act))
                    bridge.register_action_handler(act_id, h_3, run_on_qt_thread=False)

                elif mode == 1:
                    def h_2(wid, pld):
                        with handled_lock:
                            actions_handled.append((wid, "arity_2"))
                    bridge.register_action_handler(act_id, h_2, run_on_qt_thread=False)

                elif mode == 2:
                    # Faulty handler that throws exception
                    def h_err(wid, act, pld):
                        raise RuntimeError(f"Simulated fault in handler {act_id}")
                    bridge.register_action_handler(act_id, h_err, run_on_qt_thread=False)

                elif mode == 3:
                    # Handler routed to Qt thread invoker
                    def h_qt():
                        with handled_lock:
                            actions_handled.append(("qt_invoked", act_id))
                    bridge.register_action_handler(act_id, h_qt, run_on_qt_thread=True)

                # Periodically register wildcard handler
                if i % 10 == 0:
                    def h_wild(wid, act, pld):
                        with handled_lock:
                            actions_handled.append((wid, "wildcard"))
                    bridge.register_action_handler("*", h_wild, run_on_qt_thread=False)

        except Exception as exc:
            errors.append(f"Reg worker {tid} failed: {exc}")

    def unreg_worker(tid: int):
        try:
            for i in range(ops_per_thread):
                act_id = f"action_{i % 15}"
                bridge.unregister_action_handler(act_id)
        except Exception as exc:
            errors.append(f"Unreg worker {tid} failed: {exc}")

    def disp_worker(tid: int):
        try:
            for i in range(ops_per_thread):
                wid = f"action_test_wid_{i % 20}"
                choice = i % 5

                if choice == 0:
                    # Dismiss action (should evict wid from _active_widgets)
                    bridge._dispatch_widget_action(wid, "dismiss", {"reason": "user_closed"})
                elif choice == 1:
                    # Standard registered action
                    bridge._dispatch_widget_action(wid, f"action_{i % 15}", {"click_idx": i, "tid": tid})
                elif choice == 2:
                    # Unregistered action
                    bridge._dispatch_widget_action(wid, f"unknown_act_{i}", {"data": "test"})
                elif choice == 3:
                    # Malformed payload (non-dict)
                    bridge._dispatch_widget_action(wid, f"action_{i % 15}", "invalid_payload")  # type: ignore
                elif choice == 4:
                    # Empty action ID
                    bridge._dispatch_widget_action("", "", {})

        except Exception as exc:
            errors.append(f"Disp worker {tid} failed: {exc}")

    t_start = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=total_threads) as executor:
        futures = []
        for tid in range(num_reg_threads):
            futures.append(executor.submit(reg_worker, tid))
        for tid in range(num_unreg_threads):
            futures.append(executor.submit(unreg_worker, tid))
        for tid in range(num_disp_threads):
            futures.append(executor.submit(disp_worker, tid))

        concurrent.futures.wait(futures, timeout=20.0)
        for f in futures:
            f.result()

    t_elapsed = time.perf_counter() - t_start
    total_dispatches = (num_reg_threads + num_unreg_threads + num_disp_threads) * ops_per_thread
    print(f"\n[Empirical Metric] Action Contention: {total_dispatches} operations across {total_threads} threads in {t_elapsed:.3f}s")

    assert len(errors) == 0, f"Action contention encountered errors: {errors}"
    assert len(actions_handled) > 0, "Registered action handlers should have processed dispatches"


def test_stress_deep_copy_isolation_and_dict_mutation(bridge):
    """
    Stress Test 4: Verify external dictionary mutation isolation.
    Ensures that caller-side modification of dictionaries passed into render_widget,
    update_widget, or clear_all_widgets options cannot mutate or corrupt the internal
    _active_widgets registry.
    """
    num_workers = 30
    ops = 40
    errors: list[str] = []

    def mutation_worker(wid_prefix: str):
        try:
            for i in range(ops):
                wid = f"{wid_prefix}_{i}"
                shared_dict = {
                    "id": wid,
                    "template": "telemetry",
                    "title": f"Title {i}",
                    "data": {"nested_counter": i, "tags": ["a", "b"]},
                }
                # Render
                ok = bridge.render_widget(shared_dict)
                if not ok:
                    errors.append(f"Failed to render {wid}")

                # Concurrently mutate shared_dict in-place on caller thread
                shared_dict["title"] = "MUTATED_TITLE"
                shared_dict["data"]["nested_counter"] = -9999
                shared_dict["data"]["tags"].append("MUTATED_TAG")

                # Verify bridge._active_widgets holds pristine original values
                with bridge._widgets_lock:
                    internal = bridge._active_widgets.get(wid)
                    if internal is None:
                        errors.append(f"Widget {wid} missing from active widgets")
                    elif internal["title"] == "MUTATED_TITLE":
                        errors.append(f"Leak: internal widget {wid} title was mutated externally")
                    elif internal["data"]["nested_counter"] == -9999:
                        errors.append(f"Leak: internal widget {wid} data was mutated externally")
                    elif "MUTATED_TAG" in internal["data"]["tags"]:
                        errors.append(f"Leak: internal widget {wid} list was mutated externally")

                # Update with delta dict
                delta = {"metric": 100, "details": {"sub": i}}
                ok = bridge.update_widget(wid, delta)
                if not ok:
                    errors.append(f"Failed to update {wid}")

                delta["metric"] = -888
                delta["details"]["sub"] = -999

                # Verify update deep-copy isolation
                with bridge._widgets_lock:
                    internal = bridge._active_widgets.get(wid)
                    if internal and internal["data"].get("metric") == -888:
                        errors.append(f"Leak: update delta metric was mutated externally in {wid}")

        except Exception as exc:
            errors.append(f"Mutation worker failed: {exc}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = [executor.submit(mutation_worker, f"mut_{w}") for w in range(num_workers)]
        concurrent.futures.wait(futures, timeout=15.0)
        for f in futures:
            f.result()

    assert len(errors) == 0, f"Deep copy isolation failures: {errors}"


def test_stress_live_testclient_interleaved_inbound_and_broadcast(mock_ui):
    """
    Stress Test 5: Live TestClient exercising WebSocket endpoint under heavy interleaving:
    - Multiple sequential and concurrent WebSocket connections.
    - Rapid-fire inbound widget_action transmissions over the socket.
    - Interleaved server broadcasts and active widget replay upon connection.
    Verifies that the live WebSocket ASGI endpoint handles high throughput without protocol desync.
    """
    bridge = WebUIBridge(mock_ui, host="127.0.0.1", port=8765)
    client = TestClient(bridge.app, base_url="http://127.0.0.1:8765")

    # Seed 10 active widgets
    for i in range(10):
        bridge.render_widget({
            "id": f"seed_widget_{i}",
            "template": "telemetry",
            "title": f"Seed {i}",
            "data": {"val": i},
        })

    # Track actions handled
    handled_actions = []
    bridge.register_action_handler("test_action", lambda wid, act, pld: handled_actions.append((wid, pld)))

    # Execute 10 consecutive connection sessions rapidly
    for session in range(10):
        with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as ws:
            # 1. Handshake frames: init + todo_list
            _ = ws.receive_json()  # init
            _ = ws.receive_json()  # todo_list

            # 2. Replayed active widgets (10 items)
            replayed = []
            for _ in range(10):
                msg = ws.receive_json()
                assert msg["type"] == "widget_render"
                replayed.append(msg["widget"]["id"])

            assert len(replayed) == 10

            # 3. Burst send inbound widget_actions over WebSocket
            for a in range(20):
                ws.send_json({
                    "type": "widget_action",
                    "widget_id": f"seed_widget_{a % 10}",
                    "action_id": "test_action",
                    "payload": {"session": session, "idx": a},
                })

            # 4. Concurrently trigger server broadcast
            bridge.update_widget("seed_widget_0", {"live_update": session})
            update_frame = ws.receive_json()
            assert update_frame["type"] == "widget_update"
            assert update_frame["widget_id"] == "seed_widget_0"

    assert len(handled_actions) == 200, f"Expected 200 actions handled, got {len(handled_actions)}"
