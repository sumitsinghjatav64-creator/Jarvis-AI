# Handoff Report: WebBridge WebSocket & Thread Safety Analysis (Milestone 3)

**Author**: Milestone 3 Explorer 1 (`teamwork_explorer_m3_1`)  
**Target Recipient**: Orchestrator (`6906300c-9137-4e62-90d0-c438dc9f10d1`)  
**Scope**: In-depth analysis of `web_bridge.py` WebSocket endpoint (`/ws`), active connection tracking, thread safety (`_QtMainThreadInvoker`), outbound broadcasting, and event loop mechanics for Milestone 3.  
**Mode**: Read-only Investigation (No source code files modified).

---

## 1. Observation

### 1.1 Existing WebSocket Server & Loop Architecture in `web_bridge.py`
1. **Thread Creation & Event Loop Lifecycle** (`web_bridge.py:540-645`):
   - The Uvicorn server runs inside a dedicated background thread (`self._thread = threading.Thread(target=_run, daemon=True, name="WebUIBridge")`).
   - In `_run()`, a new asyncio event loop is instantiated and bound:
     ```python
     loop = asyncio.new_event_loop()
     asyncio.set_event_loop(loop)
     self.loop = loop
     ```
   - When the server shuts down or crashes, `self.loop` is set back to `None` in the `finally` block (line 641).
2. **WebSocket Endpoint Registration** (`web_bridge.py:322-331`):
   ```python
   @self.app.websocket("/ws")
   async def websocket_endpoint(ws: WebSocket):
       if not same_origin_request(ws.headers.get("origin"), ws.headers.get("host")):
           await ws.close(code=1008, reason="Origin check failed")
           return
       await ws.accept()
       logger.info("WebSocket connection accepted.")
       with self._clients_lock:
           self.clients.add(ws)
   ```
   - Initial handshake immediately streams two messages:
     - `{"type": "init", "assistant_name": ..., "state": ..., "muted": ..., ...}` (lines 344-354)
     - `{"type": "todo_list", "tasks": todo_store.list_tasks()}` (line 355)
3. **Inbound Message Parsing Loop** (`web_bridge.py:357-368`):
   ```python
   while True:
       raw = await ws.receive_text()
       try:
           msg = json.loads(raw)
           logger.info(f"Received message: {msg}")
       except json.JSONDecodeError as e:
           logger.error(f"Failed to decode JSON: {raw}, error: {e}")
           continue
       except Exception as e:
           logger.error(f"Error processing WebSocket message: {e}")
           continue

       mtype = msg.get("type")
   ```
4. **Current Handled Inbound Message Types** (`web_bridge.py:369-503`):
   - Handled: `todo_add`, `todo_toggle`, `command`, `interrupt`, `toggle_camera`, `toggle_mute`, `confirm`, `save_api_key`, `save_voice`, `test_voice`, `ui_action`.
   - **Crucial Finding**: `widget_action` is **NOT** currently implemented in `web_bridge.py`. It falls through the `if/elif` cascade and is silently ignored.
5. **Connection Teardown & Cleanup** (`web_bridge.py:504-511`):
   ```python
   except WebSocketDisconnect:
       logger.info("WebSocket disconnected.")
   except Exception as e:
       logger.error(f"Error in WebSocket connection: {e}", exc_info=True)
   finally:
       with self._clients_lock:
           self.clients.discard(ws)
   ```

### 1.2 Thread Marshaling Mechanism (`_QtMainThreadInvoker`)
1. **Invoker Implementation** (`web_bridge.py:35-48`):
   ```python
   class _QtMainThreadInvoker(QObject):
       """Thread-safe dispatcher to execute callables on the main Qt GUI thread."""
       run_callable = pyqtSignal(object)

       def __init__(self, parent=None):
           super().__init__(parent)
           self.run_callable.connect(self._execute)

       def _execute(self, fn):
           try:
               fn()
           except Exception as exc:
               logger.error("Error running UI action on Qt thread: %s", exc, exc_info=True)
   ```
2. **Invoker Instantiation & Scope** (`web_bridge.py:107-108, 136-138`):
   - Instantiated in `WebUIBridge.__init__`:
     ```python
     self._qt_invoker = _QtMainThreadInvoker(self.ui._win)
     ```
   - Invocation helper:
     ```python
     def _run_on_qt_thread(self, fn):
         """Safely schedule any function to run on the main Qt GUI thread."""
         self._qt_invoker.run_callable.emit(fn)
     ```
3. **Usage in Existing Actions** (`web_bridge.py:408-410, 433, 502`):
   - Used for `save_api_key`: `self._run_on_qt_thread(lambda k=key, o=os_name: self.ui._win._on_setup_done(k, o))`
   - Used for `save_voice`: `self._run_on_qt_thread(_apply)`
   - Used for `ui_action`: `self._run_on_qt_thread(_run_qt_action)`

### 1.3 Active Connection Tracking and `broadcast` Method
1. **Connection Set & Lock** (`web_bridge.py:95, 103`):
   ```python
   self.clients: set[WebSocket] = set()
   self._clients_lock = threading.Lock()
   ```
2. **Current `broadcast` Implementation** (`web_bridge.py:217-242`):
   ```python
   def broadcast(self, payload: dict):
       loop = self.loop
       if loop is None or not loop.is_running() or not self.clients:
           return
       data = json.dumps(payload, ensure_ascii=False)

       async def _send_all():
           with self._clients_lock:
               targets = list(self.clients)
           dead = set()
           for ws in targets:
               try:
                   await ws.send_text(data)
               except Exception:
                   dead.add(ws)
           if dead:
               with self._clients_lock:
                   self.clients.difference_update(dead)

       try:
           asyncio.run_coroutine_threadsafe(_send_all(), loop)
       except RuntimeError:
           pass
       except Exception as exc:
           logger.debug("broadcast skipped: %s", exc)
   ```

### 1.4 Frontend Interface Contract in `ui_improved.html`
1. **Frontend Dispatcher Function** (`ui_improved.html:3813-3832`):
   ```javascript
   function sendWidgetAction(widgetId, actionId, payload = {}) {
     if (typeof sfx !== 'undefined' && sfx.click) {
       sfx.click();
     }
     const message = {
       type: 'widget_action',
       widget_id: String(widgetId),
       action_id: String(actionId),
       payload: payload || {}
     };

     if (ws && ws.readyState === WebSocket.OPEN) {
       ws.send(JSON.stringify(message));
       return true;
     } else {
       console.warn('[WebBridge] Cannot dispatch widget_action; WebSocket offline', message);
       return false;
     }
   }
   window.sendWidgetAction = sendWidgetAction;
   ```
2. **Inbound Frontend Message Types Handled** (`ui_improved.html:3870-3920`):
   - Handled: `widget_render`, `widget_update`, `widget_dismiss`, `widget_clear_all`.

### 1.5 Existing Test Suite Baseline & Requirements
- Running existing tests via `C:\jarvis\Mark-LV-main\Mark-LV-main\.venv\Scripts\python.exe`:
  - `tests/test_ui_standardization.py` + `tests/test_web_bridge_e2e.py`: **37 passed in 2.13s**.
  - `tests/test_m1_challenger_stress.py` + `tests/test_m2_challenger_stress.py`: **20 passed in 6.01s**.
- In `test_m2_challenger_stress.py:255-285` (`test_ws_adversarial_malformed_widget_payloads`), tests already assert that:
  - Missing `widget_id`, missing `action_id`, non-dict payload, 64KB giant payload, and Unicode/XSS payloads do not crash the bridge.

---

## 2. Logic Chain

### 2.1 Incoming Message Parsing & Validation Logic
1. **Premise**: Inbound raw WebSocket messages arrive as strings. Currently, `web_bridge.py:359` executes `msg = json.loads(raw)`.
2. **Observation**: If a client sends valid JSON that is not a dictionary (e.g. `[1, 2, 3]` or `"plain string"` or `123`), `msg.get("type")` raises `AttributeError: 'list' object has no attribute 'get'`. Although caught by line 365 (`except Exception as e:`), this generates error tracebacks for what should be simple input validation.
3. **Inference**: Parsing should include explicit dictionary validation:
   ```python
   if not isinstance(msg, dict):
       logger.warning("Received non-dictionary JSON message: %r", type(msg))
       continue
   ```
4. **Premise**: When `mtype == "widget_action"`, the contract requires three fields: `widget_id` (str), `action_id` (str), and `payload` (dict).
5. **Observation**: Adversarial tests verify that missing `widget_id` or `action_id`, or `payload="not_dict"`, must be tolerated without disconnecting the socket.
6. **Inference**: Strict defensive extraction is required:
   ```python
   widget_id = str(msg.get("widget_id") or "").strip()
   action_id = str(msg.get("action_id") or "").strip()
   payload = msg.get("payload")
   if not isinstance(payload, dict):
       payload = {}
   if not widget_id or not action_id:
       logger.warning("Dropped invalid widget_action (missing widget_id or action_id): %s", msg)
       continue
   ```

### 2.2 Thread Safety & `_QtMainThreadInvoker` Analysis
1. **Premise**: PyQt widgets (`QWidget`, `QMainWindow`, `QWebEngineView`) and HUD state are strictly thread-affine and cannot be modified from secondary threads.
2. **Observation**: `WebUIBridge`'s WebSocket loop runs in a background thread spawned by `threading.Thread`.
3. **Observation**: `_QtMainThreadInvoker` inherits from `QObject` and is instantiated in `WebUIBridge.__init__` with `parent=self.ui._win`. In PyQt6, `QObject`'s thread affinity is determined by the thread executing the constructor (the main thread).
4. **Deduction**: When `_run_on_qt_thread(fn)` calls `self._qt_invoker.run_callable.emit(fn)` from the background thread:
   - PyQt detects cross-thread signal emission.
   - Qt automatically selects `Qt.ConnectionType.QueuedConnection`.
   - The callable `fn` is packaged into a Qt event (`QMetaCallEvent`) and posted to the main thread's event queue.
   - When the main Qt event loop processes the event, `_execute(fn)` executes on the main GUI thread.
5. **Safety Properties of `_QtMainThreadInvoker`**:
   - Complete thread safety: All UI mutations occur on the GUI thread.
   - Fault isolation: Line 46 wraps `fn()` in `try ... except Exception:` so an exception in a UI action never crashes the Qt event loop.
   - Non-blocking: `emit(fn)` returns immediately, preventing the WebSocket loop from stalling.
6. **Caveat / Traps with `_QtMainThreadInvoker`**:
   - **Late-binding closure trap**: In Python, default arguments (`lambda w=widget_id, a=action_id: ...`) MUST be used to bind loop/local variables at definition time, not runtime.
   - **Heavy work execution**: If an action does heavy computation (e.g. disk scan or synchronous web request), scheduling it on the Qt main thread will freeze the Three.js 60 FPS animation. Heavy work should remain on a background worker thread, marshaling only UI updates to Qt.

### 2.3 Active Connection Tracking & Outbound Broadcast Traps
1. **Observation**: `self.clients` is a `set[WebSocket]` protected by `self._clients_lock = threading.Lock()`.
2. **Deduction**: Adding and removing clients (`self.clients.add` and `self.clients.discard`) is properly locked in `websocket_endpoint`.
3. **Trap 1: Check-then-act without lock in `broadcast` (Line 219)**:
   - `if loop is None or not loop.is_running() or not self.clients:` evaluates `not self.clients` without acquiring `self._clients_lock`.
   - *Assessment*: In CPython, evaluating truthiness of a set is GIL-protected, but snapshotting `targets` inside the lock (`targets = list(self.clients)`) is the authoritative source. If `not self.clients` is checked, returning early when empty is a harmless optimization, but checking `not self.clients` under lock or checking `not targets` in the coroutine is cleaner.
4. **Trap 2: `asyncio.run_coroutine_threadsafe` Calling Context (Async vs Thread)**:
   - `broadcast()` is called from both external threads (Qt GUI thread, assistant background threads) AND from within the `self.loop` event loop thread (e.g. `_metrics_pusher`, or WebSocket message handlers calling `self.broadcast(...)`).
   - Calling `asyncio.run_coroutine_threadsafe(coro, loop)` when the caller is *already* running inside `loop` creates cross-thread future overhead. While it succeeds without raising an error, attempting `.result()` would cause an instant deadlock!
   - Furthermore, `asyncio.create_task(coro)` is significantly faster when already inside the event loop.
   - *Fix*: Dual-path dispatch:
     ```python
     try:
         running_loop = asyncio.get_running_loop()
     except RuntimeError:
         running_loop = None

     if running_loop is loop:
         loop.create_task(_send_all())
     else:
         asyncio.run_coroutine_threadsafe(_send_all(), loop)
     ```
5. **Trap 3: FastAPI `TestClient` and Event Loops (Crucial Test Trap)**:
   - In `test_web_bridge_e2e.py` and `test_ui_standardization.py`, `TestClient(bridge.app)` is used without calling `bridge.start()`.
   - Therefore, `bridge.loop` is `None`!
   - If `self.broadcast()` is called during a test, line 219 (`if loop is None: return`) silently ignores the broadcast. Test writers had to patch `bridge.broadcast` with `unittest.mock.MagicMock`.
   - *Fix*: In `websocket_endpoint`, capture the running loop if `self.loop is None`:
     ```python
     if self.loop is None or not self.loop.is_running():
         self.loop = asyncio.get_running_loop()
     ```
     This allows `bridge.broadcast(...)` to function seamlessly even in headless `TestClient` tests.
6. **Trap 4: Unhandled JSON Serialization Exceptions**:
   - Line 221 does `data = json.dumps(payload, ensure_ascii=False)`.
   - If `payload` contains non-JSON serializable objects (e.g. `Path`, `QColor`, `set`, numpy types), `json.dumps` raises `TypeError` immediately in the calling thread (e.g. Qt thread).
   - *Fix*: Add `default=str` and a try/except guard in `broadcast`.

---

## 3. Caveats

1. **No QWebChannel Dependency**:
   - `web_bridge.py` operates purely over WebSocket JSON protocol (`ws://127.0.0.1:8765/ws`). No `QWebChannel` or Qt WebChannel transport is used or required.
2. **Headless Execution Compatibility**:
   - In automated test runners and CI environments lacking a physical display or GPU, `QWebEngineView` cannot render, but all WebSocket routing, thread invokers, and helper methods can be tested headlessly using `PyQt6.QtWidgets.QApplication` and `fastapi.testclient.TestClient`.
3. **No Direct Return Value from `_run_on_qt_thread`**:
   - `_run_on_qt_thread` is strictly fire-and-forget. If a widget action requires a response to be sent back to the frontend, the handler must call `self.update_widget(widget_id, response_data)` or `self.broadcast(...)` rather than expecting a return value.
4. **Scope Boundaries**:
   - This analysis focuses exclusively on `web_bridge.py` WebSocket handling, connection tracking, thread safety, and backend helper methods. Audio capture and NLP streaming pipelines in `JarvisLive` are out of scope.

---

## 4. Conclusion & Recommended Architecture

### 4.1 Inbound `widget_action` Architecture in `web_bridge.py`
In `web_bridge.py` inside `websocket_endpoint`:
```python
elif mtype == "widget_action":
    widget_id = str(msg.get("widget_id") or "").strip()
    action_id = str(msg.get("action_id") or "").strip()
    payload = msg.get("payload")
    if not isinstance(payload, dict):
        payload = {}

    if not widget_id or not action_id:
        logger.warning("Received invalid widget_action (missing widget_id or action_id): %s", msg)
        continue

    self._dispatch_widget_action(widget_id, action_id, payload)
```

### 4.2 Action Dispatching & Thread-Safe Routing (`_dispatch_widget_action`)
Add action dispatching infrastructure to `WebUIBridge`:
```python
def __init__(self, ui, host: str = "127.0.0.1", port: int = 8765):
    ...
    self._action_handlers: dict[str, tuple[Callable, bool]] = {}  # action_id -> (callback, on_qt_thread)
    self.on_widget_action: Callable[[str, str, dict], Any] | None = None

def register_action_handler(self, action_id: str, callback: Callable, on_qt_thread: bool = False) -> None:
    """Register a callback for a specific widget action_id."""
    self._action_handlers[action_id] = (callback, on_qt_thread)

def _dispatch_widget_action(self, widget_id: str, action_id: str, payload: dict) -> None:
    """Safely route incoming widget actions to registered handlers or delegates."""
    try:
        # 1. Registered action-specific handler
        if action_id in self._action_handlers:
            cb, on_qt = self._action_handlers[action_id]
            if on_qt:
                self._run_on_qt_thread(lambda w=widget_id, p=payload: cb(w, p))
            else:
                cb(widget_id, payload)
            return

        # 2. Bridge-level delegate hook
        if self.on_widget_action is not None and callable(self.on_widget_action):
            self.on_widget_action(widget_id, action_id, payload)
            return

        # 3. UI-level delegate hook (if ui provides on_widget_action)
        ui_delegate = getattr(self.ui, "on_widget_action", None)
        if ui_delegate is not None and callable(ui_delegate):
            ui_delegate(widget_id, action_id, payload)
            return

        # 4. Built-in default action handling
        if action_id == "dismiss":
            self.dismiss_widget(widget_id)
        elif action_id == "refresh":
            logger.info("Widget refresh requested for %s", widget_id)
        elif action_id == "ui_action":
            # If payload specifies a classic Qt UI action (e.g. remote, customize)
            qt_act = payload.get("action")
            if qt_act:
                self._run_qt_action(qt_act)
        else:
            logger.debug("Unhandled widget action: widget=%s, action=%s", widget_id, action_id)
    except Exception as exc:
        logger.error("Error executing widget action '%s' for '%s': %s", action_id, widget_id, exc, exc_info=True)
```

### 4.3 Outbound Broadcast Hardening
Harden `broadcast(self, payload: dict)`:
```python
def broadcast(self, payload: dict):
    loop = self.loop
    if loop is None or not loop.is_running():
        return

    with self._clients_lock:
        if not self.clients:
            return

    try:
        data = json.dumps(payload, ensure_ascii=False, default=str)
    except Exception as exc:
        logger.error("Broadcast serialization error: %s", exc)
        return

    async def _send_all():
        with self._clients_lock:
            targets = list(self.clients)
        if not targets:
            return

        dead = set()
        for ws in targets:
            try:
                await ws.send_text(data)
            except Exception:
                dead.add(ws)
        if dead:
            with self._clients_lock:
                self.clients.difference_update(dead)

    try:
        running_loop = asyncio.get_running_loop()
    except RuntimeError:
        running_loop = None

    try:
        if running_loop is loop:
            loop.create_task(_send_all())
        else:
            asyncio.run_coroutine_threadsafe(_send_all(), loop)
    except RuntimeError:
        pass
    except Exception as exc:
        logger.debug("Broadcast skipped: %s", exc)
```

### 4.4 High-Level Widget Dispatch Helpers on `WebUIBridge`
```python
def render_widget(self, widget: dict) -> None:
    """Thread-safe helper to push a new widget to connected frontends."""
    if not isinstance(widget, dict):
        raise ValueError("Widget must be a dictionary.")
    self.broadcast({"type": "widget_render", "widget": widget})

def update_widget(self, widget_id: str, data: dict) -> None:
    """Thread-safe helper to update an existing widget's telemetry/state."""
    if not isinstance(data, dict):
        raise ValueError("Data must be a dictionary.")
    self.broadcast({"type": "widget_update", "widget_id": str(widget_id), "data": data})

def dismiss_widget(self, widget_id: str) -> None:
    """Thread-safe helper to dismiss a widget from the HUD dock."""
    self.broadcast({"type": "widget_dismiss", "widget_id": str(widget_id)})

def clear_all_widgets(self, target: str | None = None, immediate: bool = False) -> None:
    """Thread-safe helper to clear all widgets."""
    msg = {"type": "widget_clear_all", "immediate": immediate}
    if target:
        msg["target"] = str(target)
    self.broadcast(msg)

def broadcast_telemetry(self, metrics: dict) -> None:
    """Thread-safe helper to push diagnostic metrics to widgets."""
    if not isinstance(metrics, dict):
        raise ValueError("Metrics must be a dictionary.")
    self.broadcast({"type": "metrics", **metrics})
```

---

## 5. Verification Method

To independently verify the observations, threading properties, and proposed blueprints:

### 5.1 Run Existing Integration & Challenger Test Suites
Verify that the current codebase passes 100% of existing tests:
```powershell
& C:\jarvis\Mark-LV-main\Mark-LV-main\.venv\Scripts\python.exe -m pytest C:\jarvis\Mark-LV-main\Mark-LV-main\tests\test_ui_standardization.py C:\jarvis\Mark-LV-main\Mark-LV-main\tests\test_web_bridge_e2e.py -v
```
*Expected Result*: 37 passed.

```powershell
& C:\jarvis\Mark-LV-main\Mark-LV-main\.venv\Scripts\python.exe -m pytest C:\jarvis\Mark-LV-main\Mark-LV-main\tests\test_m1_challenger_stress.py C:\jarvis\Mark-LV-main\Mark-LV-main\tests\test_m2_challenger_stress.py -v
```
*Expected Result*: 20 passed.

### 5.2 Independent Headless Test Script for WebSocket Action Dispatch
Execute the following verification script in PowerShell:
```powershell
& C:\jarvis\Mark-LV-main\Mark-LV-main\.venv\Scripts\python.exe -c "
import json
from unittest.mock import MagicMock
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QObject, pyqtSignal
from fastapi.testclient import TestClient
from web_bridge import WebUIBridge

app = QApplication.instance() or QApplication(['test'])

class MockWin(QObject):
    _cam_stream_sig = pyqtSignal(bool)
    _cam_frame_sig = pyqtSignal(bytes)
    def __init__(self):
        super().__init__()
        self.hud = MagicMock(state='LISTENING')

ui = MagicMock()
ui._win = MockWin()
ui.assistant_name = 'JARVIS'
ui.muted = False

bridge = WebUIBridge(ui, port=8765)
client = TestClient(bridge.app, base_url='http://127.0.0.1:8765')

with client.websocket_connect('/ws', headers={'origin': 'http://testserver'}) as ws:
    msg1 = ws.receive_json()
    assert msg1['type'] == 'init'
    msg2 = ws.receive_json()
    assert msg2['type'] == 'todo_list'

    # Test widget_action tolerance
    ws.send_json({'type': 'widget_action', 'widget_id': 'test_w', 'action_id': 'click', 'payload': {'val': 1}})
    ws.send_json({'type': 'interrupt'})

ui.on_interrupt.assert_called_once()
print('SUCCESS: WebSocket connection and action tolerance independently verified.')
"
```
*Expected Result*: Prints `SUCCESS: WebSocket connection and action tolerance independently verified.`

### 5.3 Invalidation Conditions
- If Qt's event loop is not running on the main thread, cross-thread `_QtMainThreadInvoker` signals will queue indefinitely without execution.
- If `same_origin_request` rejects the Origin header (e.g. non-local Origin), WebSocket connection closes with 1008.
