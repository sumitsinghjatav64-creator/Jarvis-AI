## 2026-10-31T11:45:15Z
[Message] timestamp=2026-10-31T11:45:15Z sender=6906300c-9137-4e62-90d0-c438dc9f10d1 priority=MESSAGE_PRIORITY_HIGH content=You are Milestone 3 Implementation Worker (teamwork_worker).

## Mandatory Reference Documents
Read these files before taking any action:
1. ORIGINAL_REQUEST.md: C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\ORIGINAL_REQUEST.md
2. Master Project Spec: C:\jarvis\Mark-LV-main\Mark-LV-main\PROJECT.md
3. M3 Explorer 1 Handoff: C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\teamwork_explorer_m3_1\handoff.md
4. M3 Explorer 2 Handoff & Implementation Blueprints: C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\teamwork_explorer_m3_2\handoff.md
5. M3 Spec Miner Test Contracts: C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\teamwork_spec_miner_m3_3\handoff.md
6. Target Code: C:\jarvis\Mark-LV-main\Mark-LV-main\web_bridge.py

## Working Directory
Your working directory is:
C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\teamwork_worker_m3

Maintain progress.md and BRIEFING.md in your working directory.

## Write Ownership
You EXCLUSIVELY own and are permitted to modify/create:
1. `C:\jarvis\Mark-LV-main\Mark-LV-main\web_bridge.py`
2. `C:\jarvis\Mark-LV-main\Mark-LV-main\tests\test_m3_web_bridge_widgets.py`

Do NOT modify any other existing project files.

## MANDATORY INTEGRITY WARNING
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## Objective & Implementation Tasks

Implement bi-directional WebBridge communication in `web_bridge.py` and author comprehensive test suite in `tests/test_m3_web_bridge_widgets.py`:

### Task 1: WebUIBridge Enhancements (`web_bridge.py`)
Refer to the implementation blueprints in `teamwork_explorer_m3_2/handoff.md` and `teamwork_explorer_m3_1/handoff.md`:
1. **Initialize State in `WebUIBridge.__init__`**:
   - `self._action_handlers: dict[str, tuple[Callable, bool]] = {}` (mapping `action_id` -> `(callback, run_on_qt_thread)`)
   - `self.on_widget_action: Callable[[str, str, dict], Any] | None = None`
   - `self._active_widgets: dict[str, dict] = {}`
   - `self._widgets_lock = threading.Lock()`
2. **Implement Helper Methods on `WebUIBridge`**:
   - `render_widget(self, widget: dict) -> bool`: Validates dictionary with an `id`, tracks in `self._active_widgets` under lock, and broadcasts `{"type": "widget_render", "widget": widget}`. Returns boolean.
   - `update_widget(self, widget_id: str, data: dict) -> bool`: Validates non-empty string ID and dictionary `data`, merges into active widget tracking under lock, and broadcasts `{"type": "widget_update", "widget_id": widget_id, "data": data}`. Returns boolean.
   - `dismiss_widget(self, widget_id: str) -> bool`: Validates string ID, evicts from `self._active_widgets` under lock, and broadcasts `{"type": "widget_dismiss", "widget_id": widget_id}`. Returns boolean.
   - `clear_all_widgets(self, target: str | None = None, immediate: bool = False, options: dict | None = None) -> bool`: Clears active widgets (filtered by target if specified), and broadcasts `{"type": "widget_clear_all", "target": target, "immediate": immediate, "options": options or {"immediate": immediate}}`. Aliased as `clear_widgets`. Returns boolean.
   - `broadcast_telemetry(self, metrics: dict) -> bool`: Validates dictionary and broadcasts `{"type": "metrics", **metrics}`. Returns boolean.
   - `register_action_handler(self, action_id: str, callback: Callable, run_on_qt_thread: bool = False) -> None`: Registers callback for action ID.
   - `_dispatch_widget_action(self, widget_id: str, action_id: str, payload: dict) -> None`:
     Safely routes action:
     a) To registered handler in `self._action_handlers[action_id]`. If `run_on_qt_thread` is True, marshals via `self._run_on_qt_thread`; otherwise executes in background/thread. Supports variable callback signatures.
     b) To `self.on_widget_action(widget_id, action_id, payload)` if set.
     c) To `self.ui.on_widget_action(widget_id, action_id, payload)` if present on `self.ui`.
     d) If `action_id == "dismiss"`, evicts `widget_id` from `self._active_widgets`.
3. **Expose Helpers in `_hook_ui_methods`**:
   - Dynamically bind helper methods to `self.ui`:
     `self.ui.render_widget = self.render_widget`
     `self.ui.update_widget = self.update_widget`
     `self.ui.dismiss_widget = self.dismiss_widget`
     `self.ui.clear_all_widgets = self.clear_all_widgets`
     `self.ui.clear_widgets = self.clear_all_widgets`
     `self.ui.broadcast_telemetry = self.broadcast_telemetry`
     `self.ui.register_action_handler = self.register_action_handler`
4. **WebSocket Loop Updates in `websocket_endpoint`**:
   - Auto-detect loop if `self.loop is None`:
     ```python
     if self.loop is None or not self.loop.is_running():
         self.loop = asyncio.get_running_loop()
     ```
   - Replay active widgets after `todo_list`:
     ```python
     with self._widgets_lock:
         active_items = list(self._active_widgets.values())
     for w in active_items:
         await ws.send_text(json.dumps({"type": "widget_render", "widget": w}, ensure_ascii=False))
     ```
   - Add inbound `widget_action` handler:
     ```python
     elif mtype == "widget_action":
         widget_id = str(msg.get("widget_id") or "").strip()
         action_id = str(msg.get("action_id") or "").strip()
         payload = msg.get("payload")
         if not isinstance(payload, dict):
             payload = {}
         if not widget_id or not action_id:
             logger.warning("Dropped invalid widget_action: %s", msg)
             continue
         self._dispatch_widget_action(widget_id, action_id, payload)
     ```
5. **Broadcast Hardening**:
   - Add `default=str` to `json.dumps(payload, ensure_ascii=False, default=str)`.
   - Dual-path event loop dispatch (`create_task` if running inside `loop`, else `asyncio.run_coroutine_threadsafe`).

### Task 2: Authored Test Suite (`tests/test_m3_web_bridge_widgets.py`)
Create a comprehensive test suite covering all Milestone 3 features:
1. `test_render_widget_dispatch_and_ws_broadcast`
2. `test_update_widget_dispatch_and_ws_broadcast`
3. `test_dismiss_widget_dispatch_and_ws_broadcast`
4. `test_clear_all_widgets_dispatch_and_ws_broadcast`
5. `test_broadcast_telemetry`
6. `test_zero_clients_dispatch_safety` (calling helpers with no clients connected returns cleanly without raising)
7. `test_inbound_widget_action_routing_to_registered_handler`
8. `test_inbound_widget_action_routing_with_qt_invoker`
9. `test_inbound_widget_action_routing_to_ui_delegate`
10. `test_inbound_widget_action_malformed_tolerance` (missing widget_id, missing action_id, non-dict payload, giant string)
11. `test_active_widget_tracking_and_reconnection_replay`
12. `test_multithreaded_concurrent_widget_dispatch` (50 concurrent threads calling render/update/dismiss)
13. `test_hooked_ui_methods_delegation`

### Task 3: Mandatory Verification
Run and verify all test suites from `C:\jarvis\Mark-LV-main\Mark-LV-main`:
1. `.\.venv\Scripts\python.exe -m pytest tests/test_m3_web_bridge_widgets.py -v`
2. `.\.venv\Scripts\python.exe -m pytest tests/test_web_bridge_e2e.py -v`
3. `.\.venv\Scripts\python.exe -m pytest tests/test_m2_challenger_stress.py -v`
4. `.\.venv\Scripts\python.exe -m pytest` (full regression test suite)
5. `node tests/test_widget_manager_oracle.js`

Write your complete handoff report in `C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\teamwork_worker_m3\handoff.md`.
Then send a completion message back to the orchestrator (conversation ID: 6906300c-9137-4e62-90d0-c438dc9f10d1).
