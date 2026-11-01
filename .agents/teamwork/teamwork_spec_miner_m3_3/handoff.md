# Handoff Report: Milestone 3 Test Contracts & Specification Mining

**Author**: Milestone 3 Spec Miner (`teamwork_spec_miner`)  
**Working Directory**: `C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\teamwork_spec_miner_m3_3`  
**Recipient**: Orchestrator (`6906300c-9137-4e62-90d0-c438dc9f10d1`)  
**Status**: Hard Handoff (Investigation & Specification Complete)  

---

## 1. Observation

### 1.1 Master Specs & Requirements
1. **ORIGINAL_REQUEST.md** (lines 15–17, 24–27):
   - "R2. Generative UI Enhancement: Equip the WebEngine HUD interface in `ui_improved.html` with generative UI capabilities to dynamically render interactive dashboard widgets, live diagnostics, and modern visual controls alongside the core Three.js visualization, communicating bi-directionally via `web_bridge.py`."
   - "Generative UI controls communicate bi-directionally with the backend through `web_bridge.py`."
2. **PROJECT.md** (lines 8–10, 21–24, 39–81):
   - Feature 7: "Inbound `widget_action` WebSocket Handler: Extend `web_bridge.py` WebSocket loop to parse and handle `widget_action` messages from frontend widgets."
   - Feature 8: "Backend Widget Dispatch & Telemetry Helpers: Methods on `WebUIBridge` (`render_widget`, `update_widget`, `dismiss_widget`, and telemetry broadcasts) thread-safely invokable from Qt/Jarvis."
   - Defines interface contracts for `widget_render`, `widget_update`, `widget_dismiss`, and `widget_action`.

### 1.2 Frontend Implementation in `ui_improved.html`
1. **WebSocket Inbound Handlers** (`ui_improved.html`, lines 3405–3425):
   ```javascript
   // === GENERATIVE UI WEBSOCKET HANDLERS ===
   else if (msg.type === 'widget_render') {
     if (msg.widget && window.widgetManager) {
       window.widgetManager.renderWidget(msg.widget);
     }
   }
   else if (msg.type === 'widget_update') {
     if (msg.widget_id && window.widgetManager) {
       window.widgetManager.updateWidget(msg.widget_id, msg.data || {});
     }
   }
   else if (msg.type === 'widget_dismiss') {
     if (msg.widget_id && window.widgetManager) {
       window.widgetManager.dismissWidget(msg.widget_id);
     }
   }
   else if (msg.type === 'widget_clear_all') {
     if (window.widgetManager) {
       window.widgetManager.clearAll(msg.target, msg.options || (msg.immediate !== undefined ? { immediate: Boolean(msg.immediate) } : {}));
     }
   }
   ```
2. **Outbound Action Dispatcher** (`ui_improved.html`, lines 3813–3831, 3149–3155):
   ```javascript
   function sendWidgetAction(widgetId, actionId, payload = {}) {
     const message = {
       type: 'widget_action',
       widget_id: String(widgetId),
       action_id: String(actionId),
       payload: payload || {}
     };
     if (ws && ws.readyState === WebSocket.OPEN) {
       ws.send(JSON.stringify(message));
       return true;
     }
     ...
   }
   ```
3. **Widget Lifecycle Engine** (`ui_improved.html`, lines 2885–3160):
   - `WidgetManager` manages widget lifecycle, supports templates (`telemetry`, `activity_tracker`, `action_grid`, `custom`), auto-dismiss timer (`ttl_ms` / `auto_dismiss_ms`), targets (`dock` vs `chat`), FIFO eviction (max 4 widgets in dock), and cached sub-element delta updating.

### 1.3 Backend State in `web_bridge.py`
1. **WebSocket Receive Loop** (`web_bridge.py`, lines 357–503):
   - Parses inbound JSON: `msg = json.loads(raw)`.
   - Handles `todo_add`, `todo_toggle`, `command`, `interrupt`, `toggle_camera`, `toggle_mute`, `confirm`, `save_api_key`, `save_voice`, `test_voice`, `ui_action`.
   - Currently has **NO branch** for `mtype == "widget_action"`! Inbound `widget_action` messages fall through as unhandled and are silently ignored.
2. **Broadcast Mechanism** (`web_bridge.py`, lines 217–242):
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
   - If `self.clients` is empty or `self.loop` is None/stopped, `broadcast` returns immediately without error.
   - However, `WebUIBridge` currently lacks high-level helper methods: `render_widget`, `update_widget`, `dismiss_widget`, `clear_widgets`.

### 1.4 Existing Test Baseline
1. Executed full test suite:
   `& C:\jarvis\Mark-LV-main\Mark-LV-main\.venv\Scripts\python.exe -m pytest --rootdir=C:\jarvis\Mark-LV-main\Mark-LV-main C:\jarvis\Mark-LV-main\Mark-LV-main\tests -q`
   Result: **146 passed, 1 skipped, 2 warnings in 14.74s**.
2. `tests/test_web_bridge_e2e.py` lines 395–412:
   `test_ws_widget_action_message_tolerance` verifies that sending `widget_action` over `/ws` does not crash the bridge.
3. `tests/test_m2_challenger_stress.py` lines 255–287:
   `test_ws_adversarial_malformed_widget_payloads` verifies socket survives malformed/adversarial `widget_action` payloads (missing fields, non-dict payloads, 64KB giant strings, XSS strings).

---

## 2. Logic Chain

1. **Premise 1**: The client-side Generative UI in `ui_improved.html` (Milestone 2) sends `widget_action` JSON messages over `/ws` with keys `type: "widget_action"`, `widget_id: str`, `action_id: str`, `payload: dict`.
2. **Premise 2**: In `web_bridge.py`, the WebSocket handler inspects `mtype = msg.get("type")`. Currently, `widget_action` is not recognized, so user interactions on widgets (button clicks, toggles, dismissals) cannot invoke backend logic.
3. **Inference 1**: To satisfy Milestone 3 Feature 7, `web_bridge.py` must implement an `elif mtype == "widget_action":` block that validates `widget_id`, `action_id`, and `payload`, and routes the action to a registered handler or `ui.on_widget_action`.
4. **Premise 3**: In `ui_improved.html`, `ws.onmessage` expects outbound server messages of types: `widget_render`, `widget_update`, `widget_dismiss`, and `widget_clear_all`.
5. **Premise 4**: Backend callers (Jarvis voice assistant, autonomous agents, telemetry loops, Qt callbacks) require Pythonic, thread-safe methods on `WebUIBridge` rather than manually formatting raw dictionary payloads.
6. **Inference 2**: To satisfy Milestone 3 Feature 8, `WebUIBridge` must implement:
   - `render_widget(self, widget: dict) -> bool`
   - `update_widget(self, widget_id: str, data: dict) -> bool`
   - `dismiss_widget(self, widget_id: str) -> bool`
   - `clear_widgets(self, target: str | None = None, options: dict | None = None) -> bool` (aliased as `clear_all_widgets`)
7. **Premise 5**: Qt GUI operations or asynchronous worker threads call bridge methods at arbitrary times, including when no browser/WebEngine client is connected, before the bridge starts, or concurrently across multiple threads.
8. **Inference 3**: Dispatch helpers must guarantee that:
   - Calling dispatch helpers when `clients` is empty or `loop` is `None` returns cleanly without raising an exception.
   - Calling dispatch helpers concurrently from 50+ threads is free of race conditions or data corruption.
   - Malformed payloads (missing fields, non-dict, non-JSON strings, oversized payloads) are handled defensively without terminating the WebSocket session.

---

## 3. Caveats

1. **Qt Thread Marshaling**: In PyQt6, GUI operations (such as updating Qt widgets or displaying native dialogs) must occur on the main Qt thread. If an inbound `widget_action` triggers a Qt GUI update, it should be scheduled via `self._run_on_qt_thread(fn)`. For headless tests, `mock_ui` or callable handlers running directly in the bridge event loop thread are used.
2. **Read-Only Spec Mining**: In accordance with the role instructions, no implementation code was edited or written during this task.
3. **No Other Caveats**: All interface contracts were extracted from authoritative codebase files (`web_bridge.py`, `ui_improved.html`, `PROJECT.md`, `tests/test_web_bridge_e2e.py`).

---

## 4. Features Discovered

| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|----------|---------|-------------|--------|---------|----------------|----------------|
| 1 | Inbound WS | Inbound `widget_action` Dispatch | Receives widget interaction events from `ui_improved.html` and dispatches to Python handler | JSON string: `{"type": "widget_action", "widget_id": str, "action_id": str, "payload": dict}` | Invokes `on_widget_action(widget_id, action_id, payload)` | If missing fields or non-dict, logs warning and ignores without closing WS | `ui_improved.html:3818`, `PROJECT.md:76` |
| 2 | Outbound WS | `widget_render` Dispatch | Dispatches declarative widget schema to render new card in dock or chat | Python `widget: dict` containing `id`, `template`, `title`, `icon`, `target`, `data`, `actions`, `ttl_ms` | WS JSON: `{"type": "widget_render", "widget": {...}}` | Rejects non-dict widget input (returns False / logs error); safe if no clients connected | `PROJECT.md:41`, `ui_improved.html:3406` |
| 3 | Outbound WS | `widget_update` Dispatch | Broadcasts real-time delta updates to an existing mounted widget | `widget_id: str`, `data: dict` | WS JSON: `{"type": "widget_update", "widget_id": str, "data": {...}}` | Validates `widget_id` is string and `data` is dict; returns False if invalid; safe if no clients | `PROJECT.md:58`, `ui_improved.html:3411` |
| 4 | Outbound WS | `widget_dismiss` Dispatch | Instructs frontend to smoothly animate and remove widget from DOM | `widget_id: str` | WS JSON: `{"type": "widget_dismiss", "widget_id": str}` | Validates non-empty string ID; returns False if invalid; safe if no clients | `PROJECT.md:65`, `ui_improved.html:3416` |
| 5 | Outbound WS | `widget_clear_all` Dispatch | Instructs frontend to tear down all widgets (optionally filtered by target) | `target: Optional[str]`, `options: Optional[dict]` | WS JSON: `{"type": "widget_clear_all", ["target": str], ["options": dict]}` | Safe when target is None; ignores invalid options; safe if no clients | `ui_improved.html:3421`, Dispatch Assignment |
| 6 | Bridge Core | Action Handler Registration | Allows registering custom callback callable on `WebUIBridge` for inbound actions | `handler: Callable[[str, str, dict], None]` | Stored on `bridge._widget_action_handler` | Replaces or supplements `ui.on_widget_action` | Design Analysis |
| 7 | Core Security | Inbound Origin Verification | Enforces local loopback origin check on WebSocket handshake | WS `Origin` and `Host` headers | Code 1008 Reject if untrusted origin | Rejects cross-site connections | `web_bridge.py:324` |
| 8 | Core Reliability | Zero-Client Dispatch Safety | Ensures calling dispatch helpers when no clients are connected does not fail | Any dispatch call | Returns cleanly (or False/True) | No exception raised | Dispatch Assignment |
| 9 | Core Concurrency | Multi-Threaded Dispatch Safety | Safe concurrent calls to `render_widget`, `update_widget`, `broadcast` from 50+ threads | Concurrent Python threads calling bridge helpers | Ordered WebSocket frame queuing | Thread-safe locks protect client sets and loop operations | `web_bridge.py:224` |

---

## 5. Edge Cases

| # | Feature | Input | Observed / Required Behavior |
|---|---------|-------|-------------------------------|
| 1 | `widget_action` | Missing `widget_id` (`{"type": "widget_action", "action_id": "act"}`) | Must NOT crash receive loop. Logs warning; ignores message. WebSocket remains open and responsive. |
| 2 | `widget_action` | Missing `action_id` (`{"type": "widget_action", "widget_id": "w1"}`) | Must NOT crash receive loop. Logs warning; ignores message. WebSocket remains open and responsive. |
| 3 | `widget_action` | Non-dict `payload` (`"payload": "string"` or `"payload": 123` or `"payload": [1,2]`) | Reject or coerce safely. Must NOT raise `AttributeError` or unhandled exception. |
| 4 | `widget_action` | Missing `payload` (`{"type": "widget_action", "widget_id": "w1", "action_id": "act"}`) | Defaults `payload` to empty dictionary `{}`; invokes handler cleanly. |
| 5 | `widget_action` | Giant 64KB+ JSON string payload | Bridge parses JSON safely without memory corruption; delivers dict to handler; subsequent commands unaffected. |
| 6 | `widget_action` | Hostile injection strings (`'; DROP TABLE...`, `<script>alert(1)</script>`, Unicode emojis `🚀`) | Treated strictly as literal string values; no unescaping or execution. |
| 7 | `widget_action` | Non-JSON text frame (`{{malformed...`) | Caught by existing `json.JSONDecodeError` handler; logged; connection kept alive. |
| 8 | `render_widget` | Called when `self.clients` is empty (`set()`) | Returns cleanly without exception. |
| 9 | `render_widget` | Called when `self.loop` is `None` (server not started) | Returns cleanly without exception. |
| 10 | `render_widget` | Non-dict input (`render_widget("invalid")` or `render_widget(None)`) | Returns `False` or raises clean `TypeError`; does not broadcast corrupted frame. |
| 11 | `render_widget` | Missing `id` in `widget` dictionary | Auto-generates unique string ID (`f"widget_{time.time_ns()}"`) before dispatching. |
| 12 | `update_widget` | Called with empty string or non-string `widget_id` | Returns `False` / logs error; does not broadcast. |
| 13 | `update_widget` | Called with non-dict `data` (`data="text"`) | Returns `False` / logs error; does not broadcast. |
| 14 | `dismiss_widget` | Called with empty string or non-string `widget_id` | Returns `False` / logs error; does not broadcast. |
| 15 | `clear_widgets` | Called with invalid `target` (`target=123` or `target="invalid"`) | Coerces or sanitizes target; defaults to all targets if unspecified. |
| 16 | Concurrency | 50 concurrent threads firing 500 calls to `update_widget` and `render_widget` | All coroutines submitted via `run_coroutine_threadsafe`; client set mutations protected by `_clients_lock`; zero race conditions or deadlocks. |
| 17 | Client Disconnect | Client terminates abruptly while server is broadcasting `widget_update` burst | Exception caught per client; dead socket removed from `self.clients`; remaining clients unaffected. |

---

## 6. Exact Message Schemas Specification

### 6.1 Inbound Schema: `widget_action`
- **Source**: WebEngine HUD (`ui_improved.html`)
- **Destination**: `WebUIBridge` (`/ws` loop)
- **JSON Schema**:
  ```json
  {
    "type": "object",
    "required": ["type", "widget_id", "action_id"],
    "properties": {
      "type": { "type": "string", "enum": ["widget_action"] },
      "widget_id": { "type": "string", "minLength": 1 },
      "action_id": { "type": "string", "minLength": 1 },
      "payload": { "type": "object", "default": {} }
    },
    "additionalProperties": true
  }
  ```
- **Example Wire Payload**:
  ```json
  {
    "type": "widget_action",
    "widget_id": "diag_sys_status",
    "action_id": "refresh",
    "payload": {
      "force": true,
      "source": "gen_ui_dock"
    }
  }
  ```

### 6.2 Outbound Schema: `widget_render`
- **Source**: `WebUIBridge.render_widget`
- **Destination**: WebEngine HUD (`WidgetManager.renderWidget`)
- **JSON Schema**:
  ```json
  {
    "type": "object",
    "required": ["type", "widget"],
    "properties": {
      "type": { "type": "string", "enum": ["widget_render"] },
      "widget": {
        "type": "object",
        "required": ["id"],
        "properties": {
          "id": { "type": "string", "minLength": 1 },
          "template": {
            "type": "string",
            "enum": ["telemetry", "activity_tracker", "action_grid", "custom"],
            "default": "custom"
          },
          "title": { "type": "string", "default": "" },
          "icon": { "type": "string", "default": "cpu" },
          "target": { "type": "string", "enum": ["dock", "chat"], "default": "dock" },
          "data": { "type": "object", "default": {} },
          "actions": {
            "type": "array",
            "items": {
              "type": "object",
              "required": ["action_id", "label"],
              "properties": {
                "action_id": { "type": "string" },
                "label": { "type": "string" },
                "variant": { "type": "string", "enum": ["primary", "secondary", "danger", "ghost"], "default": "primary" },
                "icon": { "type": "string" },
                "toggle": { "type": "boolean", "default": false },
                "active": { "type": "boolean", "default": false },
                "payload": { "type": "object", "default": {} }
              }
            },
            "default": []
          },
          "ttl_ms": { "type": "integer", "minimum": 0 },
          "auto_dismiss_ms": { "type": "integer", "minimum": 0 }
        }
      }
    }
  }
  ```
- **Example Wire Payload**:
  ```json
  {
    "type": "widget_render",
    "widget": {
      "id": "diag_sys_status",
      "template": "telemetry",
      "title": "System Diagnostics",
      "icon": "cpu",
      "target": "dock",
      "data": {
        "cpu": 15.2,
        "ram": 42.1
      },
      "actions": [
        {
          "action_id": "refresh",
          "label": "Refresh",
          "variant": "primary"
        }
      ]
    }
  }
  ```

### 6.3 Outbound Schema: `widget_update`
- **Source**: `WebUIBridge.update_widget`
- **Destination**: WebEngine HUD (`WidgetManager.updateWidget`)
- **JSON Schema**:
  ```json
  {
    "type": "object",
    "required": ["type", "widget_id", "data"],
    "properties": {
      "type": { "type": "string", "enum": ["widget_update"] },
      "widget_id": { "type": "string", "minLength": 1 },
      "data": { "type": "object" }
    }
  }
  ```
- **Example Wire Payload**:
  ```json
  {
    "type": "widget_update",
    "widget_id": "diag_sys_status",
    "data": {
      "cpu": 22.0,
      "ram": 43.5
    }
  }
  ```

### 6.4 Outbound Schema: `widget_dismiss`
- **Source**: `WebUIBridge.dismiss_widget`
- **Destination**: WebEngine HUD (`WidgetManager.dismissWidget`)
- **JSON Schema**:
  ```json
  {
    "type": "object",
    "required": ["type", "widget_id"],
    "properties": {
      "type": { "type": "string", "enum": ["widget_dismiss"] },
      "widget_id": { "type": "string", "minLength": 1 }
    }
  }
  ```
- **Example Wire Payload**:
  ```json
  {
    "type": "widget_dismiss",
    "widget_id": "diag_sys_status"
  }
  ```

### 6.5 Outbound Schema: `widget_clear_all`
- **Source**: `WebUIBridge.clear_widgets`
- **Destination**: WebEngine HUD (`WidgetManager.clearAll`)
- **JSON Schema**:
  ```json
  {
    "type": "object",
    "required": ["type"],
    "properties": {
      "type": { "type": "string", "enum": ["widget_clear_all"] },
      "target": { "type": ["string", "null"], "enum": ["dock", "chat", null] },
      "options": {
        "type": "object",
        "properties": {
          "immediate": { "type": "boolean" }
        }
      }
    }
  }
  ```
- **Example Wire Payload**:
  ```json
  {
    "type": "widget_clear_all",
    "target": "dock",
    "options": {
      "immediate": false
    }
  }
  ```

---

## 7. Backend Interface Contracts (`WebUIBridge`)

The following methods must be implemented on `WebUIBridge` in `web_bridge.py`:

```python
class WebUIBridge:
    # Existing __init__, broadcast, etc.
    # ...

    def set_widget_action_handler(self, handler: Callable[[str, str, dict], None]) -> None:
        """Register a callback for inbound widget_action events."""
        self._widget_action_handler = handler

    def render_widget(self, widget: dict) -> bool:
        """
        Thread-safely broadcast a widget_render event to active UI clients.
        Generates an ID if not present in widget dict.
        Returns True if queued, False if validation fails.
        """
        if not isinstance(widget, dict):
            logger.error("render_widget: widget must be a dict, got %s", type(widget))
            return False
        widget_copy = dict(widget)
        if not widget_copy.get("id"):
            widget_copy["id"] = f"widget_{time.time_ns()}"
        self.broadcast({"type": "widget_render", "widget": widget_copy})
        return True

    def update_widget(self, widget_id: str, data: dict) -> bool:
        """
        Thread-safely broadcast a widget_update event to active UI clients.
        Returns True if queued, False if validation fails.
        """
        if not widget_id or not isinstance(widget_id, str):
            logger.error("update_widget: widget_id must be a non-empty string")
            return False
        if not isinstance(data, dict):
            logger.error("update_widget: data must be a dict, got %s", type(data))
            return False
        self.broadcast({"type": "widget_update", "widget_id": widget_id, "data": data})
        return True

    def dismiss_widget(self, widget_id: str) -> bool:
        """
        Thread-safely broadcast a widget_dismiss event to active UI clients.
        Returns True if queued, False if validation fails.
        """
        if not widget_id or not isinstance(widget_id, str):
            logger.error("dismiss_widget: widget_id must be a non-empty string")
            return False
        self.broadcast({"type": "widget_dismiss", "widget_id": widget_id})
        return True

    def clear_widgets(self, target: str | None = None, options: dict | None = None) -> bool:
        """
        Thread-safely broadcast a widget_clear_all event to active UI clients.
        target can be 'dock', 'chat', or None (clears all).
        """
        msg: dict[str, Any] = {"type": "widget_clear_all"}
        if target is not None:
            msg["target"] = str(target)
        if options is not None and isinstance(options, dict):
            msg["options"] = options
        self.broadcast(msg)
        return True

    # Ergonomic alias
    clear_all_widgets = clear_widgets
```

In the WebSocket receive loop (`websocket_endpoint`):
```python
elif mtype == "widget_action":
    widget_id = msg.get("widget_id")
    action_id = msg.get("action_id")
    payload = msg.get("payload")
    if payload is None:
        payload = {}

    if not isinstance(widget_id, str) or not widget_id.strip():
        logger.warning("Malformed widget_action: missing or invalid widget_id: %r", widget_id)
        continue
    if not isinstance(action_id, str) or not action_id.strip():
        logger.warning("Malformed widget_action: missing or invalid action_id: %r", action_id)
        continue
    if not isinstance(payload, dict):
        logger.warning("Malformed widget_action: payload must be a dict, got %r", type(payload))
        continue

    # Dispatch to registered handler or ui.on_widget_action
    handler = getattr(self, "_widget_action_handler", None)
    if callable(handler):
        try:
            handler(widget_id, action_id, payload)
        except Exception as exc:
            logger.error("Error in widget_action handler: %s", exc, exc_info=True)
    elif hasattr(self.ui, "on_widget_action") and callable(self.ui.on_widget_action):
        try:
            self.ui.on_widget_action(widget_id, action_id, payload)
        except Exception as exc:
            logger.error("Error in ui.on_widget_action: %s", exc, exc_info=True)
```

---

## 8. Milestone 3 Comprehensive Test Specification & Test Cases

The following test suite (`tests/test_m3_widget_bridge.py` or addition to `test_web_bridge_e2e.py`) must be authored to verify Milestone 3 implementation:

### 8.1 Unit Tests: Helper Methods on `WebUIBridge`
1. `test_render_widget_valid`:
   - Calls `bridge.render_widget({...})` with telemetry card.
   - Asserts `mock_broadcast` receives `{"type": "widget_render", "widget": {...}}`.
   - Returns `True`.
2. `test_render_widget_generates_id_if_missing`:
   - Calls `bridge.render_widget({"template": "custom", "data": {}})`.
   - Asserts broadcasted widget has non-empty string `id` (e.g. `widget_...`).
3. `test_render_widget_rejects_non_dict`:
   - Calls `bridge.render_widget("invalid")` and `bridge.render_widget(None)`.
   - Asserts returns `False` and `broadcast` not called.
4. `test_update_widget_valid`:
   - Calls `bridge.update_widget("card1", {"cpu": 50})`.
   - Asserts `mock_broadcast` receives `{"type": "widget_update", "widget_id": "card1", "data": {"cpu": 50}}`.
5. `test_update_widget_rejects_invalid_inputs`:
   - Calls with non-string `widget_id` (`None`, `123`, `""`) or non-dict `data` (`"not_a_dict"`).
   - Asserts returns `False` and `broadcast` not called.
6. `test_dismiss_widget_valid`:
   - Calls `bridge.dismiss_widget("card1")`.
   - Asserts `mock_broadcast` receives `{"type": "widget_dismiss", "widget_id": "card1"}`.
7. `test_dismiss_widget_rejects_invalid_id`:
   - Calls with `""` or `None`.
   - Asserts returns `False` and `broadcast` not called.
8. `test_clear_widgets_all`:
   - Calls `bridge.clear_widgets()`.
   - Asserts `mock_broadcast` receives `{"type": "widget_clear_all"}`.
9. `test_clear_widgets_target_and_options`:
   - Calls `bridge.clear_widgets(target="dock", options={"immediate": True})`.
   - Asserts payload contains `"target": "dock"` and `"options": {"immediate": True}`.
10. `test_dispatch_helpers_zero_clients`:
    - Calls `render_widget`, `update_widget`, `dismiss_widget`, `clear_widgets` when `bridge.clients` is empty.
    - Asserts no exception is raised and methods execute cleanly.
11. `test_dispatch_helpers_before_loop_started`:
    - Calls all 4 helper methods when `bridge.loop is None`.
    - Asserts no exception is raised.

### 8.2 WebSocket Integration Tests: Inbound `widget_action`
12. `test_ws_widget_action_calls_registered_handler`:
    - Registers handler with `bridge.set_widget_action_handler(mock_handler)`.
    - Sends valid `widget_action` via TestClient WebSocket.
    - Asserts `mock_handler` called with `("diag_sys_status", "refresh", {"force": True})`.
13. `test_ws_widget_action_calls_ui_on_widget_action`:
    - Defines `mock_ui.on_widget_action = MagicMock()`.
    - Sends `widget_action`.
    - Asserts `mock_ui.on_widget_action` called with expected arguments.
14. `test_ws_widget_action_malformed_missing_fields`:
    - Sends message missing `widget_id`, message missing `action_id`, and message missing both.
    - Asserts no handler called; socket remains healthy and accepts subsequent `command`.
15. `test_ws_widget_action_malformed_non_dict_payload`:
    - Sends message with `payload="string"`, `payload=[1, 2]`, `payload=123`.
    - Asserts no unhandled exception; socket remains healthy.
16. `test_ws_widget_action_empty_payload_defaults_to_dict`:
    - Sends message omitting `payload`.
    - Asserts handler called with `payload={}`.
17. `test_ws_widget_action_giant_payload`:
    - Sends message with 64KB string payload in dictionary.
    - Asserts handler receives payload without truncation or memory corruption.
18. `test_ws_widget_action_adversarial_strings`:
    - Sends action containing XSS tags, Unicode emojis, SQL injection patterns.
    - Asserts handler receives exact literal strings intact.

### 8.3 Concurrency & Multi-Threaded Stress Tests
19. `test_concurrent_dispatch_helpers_multithreaded`:
    - Uses `ThreadPoolExecutor(max_workers=16)` to execute 500 interleaved calls to `render_widget`, `update_widget`, `dismiss_widget`, `clear_widgets`.
    - Asserts all calls succeed with zero deadlocks or race conditions.
20. `test_e2e_full_widget_action_feedback_loop`:
    - WebSocket client connects.
    - Receives `init` and `todo_list`.
    - Server calls `bridge.render_widget(...)` -> client receives `widget_render`.
    - Client sends `widget_action` -> triggers action handler.
    - Handler calls `bridge.update_widget(...)` -> client receives `widget_update`.
    - Handler calls `bridge.dismiss_widget(...)` -> client receives `widget_dismiss`.

---

## 9. Verification Method

To independently verify the contracts, schemas, and specifications:

1. **Verify Existing Pytest Suite**:
   ```powershell
   & C:\jarvis\Mark-LV-main\Mark-LV-main\.venv\Scripts\python.exe -m pytest --rootdir=C:\jarvis\Mark-LV-main\Mark-LV-main C:\jarvis\Mark-LV-main\Mark-LV-main\tests -q
   ```
   *Expected outcome*: 146 passed, 1 skipped, 2 warnings.

2. **Verify Frontend Interface Extraction in `ui_improved.html`**:
   ```powershell
   Select-String -Path 'C:\jarvis\Mark-LV-main\Mark-LV-main\ui_improved.html' -Pattern 'widget_render|widget_update|widget_dismiss|widget_clear_all|widget_action'
   ```
   *Expected outcome*: Confirms lines 3406-3425 (inbound handlers) and lines 3818-3825 (outbound dispatcher).

3. **Verify Node.js Oracle Test Execution**:
   ```powershell
   node C:\jarvis\Mark-LV-main\Mark-LV-main\tests\test_widget_manager_oracle.js
   ```
   *Expected outcome*: `ALL ORACLE TESTS COMPLETED: 165 passed, 0 failed` with exit code 0.

4. **Invalidation Conditions**:
   - If `widget_render` or `widget_update` requires schemas differing from `ui_improved.html:3406-3425`, the specification would be invalidated.
   - If `WebUIBridge` cannot dispatch thread-safely via `asyncio.run_coroutine_threadsafe`, the concurrency model would require alteration. (Verified: `run_coroutine_threadsafe` is natively thread-safe in Python asyncio).
