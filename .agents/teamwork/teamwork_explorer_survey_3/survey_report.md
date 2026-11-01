# Comprehensive Survey Report: WebBridge Bi-Directional Communication & Pytest Test Suite

**Author**: Survey Explorer 3  
**Date**: 2026-10-31  
**Working Directory**: `C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\teamwork_explorer_survey_3`  
**Target Codebase**: `C:\jarvis\Mark-LV-main\Mark-LV-main`  
**Focus Areas**:
1. `web_bridge.py` bi-directional communication, WebEngine integration, threading, and messaging protocols.
2. Generative UI capabilities, dynamic widgets, interactive controls, live telemetry, and backend dispatching.
3. Existing pytest test suite audit, testing coverage gaps, and specification of new test cases for UI standardization and bi-directional communication.

---

## 1. Executive Summary

- **Bridge Architecture**: `web_bridge.py` implements a zero-config local HTTP and WebSocket bridge using **FastAPI** and **Uvicorn** running inside a dedicated background Python daemon thread (`WebUIBridge`). It does **not** use `QWebChannel`; instead, it provides a standards-compliant WebSocket interface (`ws://127.0.0.1:8765/ws`) and HTTP file server (`http://127.0.0.1:8765`), which `QWebEngineView` in `main.py` loads as a standard web application.
- **Qt Thread Safety**: `web_bridge.py` bridges async background tasks and the PyQt6 main GUI thread via `_QtMainThreadInvoker(QObject)`, which uses a PyQt `pyqtSignal(object)` connected with a queued connection to safely marshal function calls from the asyncio thread to the Qt GUI thread.
- **Generative UI Opportunity**: `ui_improved.html` currently hosts static HUD cards (Today Tasks, System Status, Quick Actions) and a Three.js WebGL particle canvas. Adding generative UI capabilities (dynamic cards for live diagnostics, telemetry, activity controls, and multi-agent states) requires defining a bi-directional JSON widget protocol over the existing WebSocket connection without interfering with Three.js rendering.
- **Test Suite Status**: The current pytest suite in `tests/` contains **22 test files** with **90 test items** (**89 passed, 1 skipped**, execution time ~7.9s). However, there is **zero existing test coverage** for `web_bridge.py`, `ui.py`, or `ui_improved.html`.
- **Headless Testability Verified**: We independently proved that `WebUIBridge` can be completely, headlessly, and deterministically tested using `fastapi.testclient.TestClient` without launching real web browsers, binding OS network sockets, or requiring a physical display.

---

## 2. In-Depth Analysis of `web_bridge.py`

### 2.1 File Information & Line Overview
- **File**: `C:\jarvis\Mark-LV-main\Mark-LV-main\web_bridge.py`
- **Total Lines**: 666 lines
- **Dependencies**: `fastapi`, `uvicorn`, `PyQt6.QtCore (QObject, pyqtSignal)`, `psutil`, `asyncio`, `threading`, `socket`, `core.confirm`, `core.todo_store`, `core.web_security.same_origin_request`, `ui._metrics`.

### 2.2 Threading Model & Qt Integration
```python
# Lines 35-48
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
- **Thread Separation**: `WebUIBridge.start()` (lines 541–661) initializes a daemon thread named `"WebUIBridge"`. It creates a new `asyncio` event loop and launches `uvicorn.Server.serve()`.
- **Marshalling into Qt**: When incoming WebSocket messages require Qt actions (e.g. `save_api_key`, `save_voice`, or `ui_action`), `self._run_on_qt_thread(fn)` emits `self._qt_invoker.run_callable.emit(fn)` (line 138). Because `_QtMainThreadInvoker` is parented to `self.ui._win` on the main GUI thread, Qt's signal-slot engine dispatches `_execute` across the thread boundary onto the main Qt event loop.

### 2.3 HTML File Discovery & Resolution (`_find_ui_file`)
```python
# Lines 50-88
def _find_ui_file() -> tuple[Path | None, list[Path]]:
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass))
        exe_dir = Path(sys.executable).parent
        candidates.append(exe_dir)
        candidates.append(exe_dir / "_internal")

    candidates.append(Path(__file__).resolve().parent)
    candidates.append(Path.cwd())
    ...
    for base in unique_candidates:
        for fname in ("ui_improved.html", "ui improved.html"):
            target = base / fname
            if target.is_file():
                return target, unique_candidates
    return None, unique_candidates
```
**Standardization Issues Identified**:
1. Line 2 (Module Docstring): references `ui improved.html`.
2. Line 52 (Function Docstring): references `Search for 'ui improved.html'`.
3. Line 82: `for fname in ("ui_improved.html", "ui improved.html"):` checks both. To enforce standardization, `ui_improved.html` should be canonical.
4. Lines 301, 305, 307: The 404 HTML fallback mentions `ui improved.html` three times:
   - Line 301: `locations_html = "<br>".join(f"• {p / 'ui improved.html'}" for p in searched_paths)`
   - Line 305: `f"<p>Could not find <code>ui improved.html</code> in any of the expected locations:</p>"`
   - Line 307: `f"<p>Please place <code>ui improved.html</code> inside your main folder or next to <code>MarkLV.exe</code>.</p>"`

### 2.4 HTTP Routes
- `GET /` (lines 295–311): Serves `ui_improved.html` (or returns structured 404 HTML if missing).
- `GET /three.min.js` (lines 285–294): Serves local `three.min.js` file with `application/javascript` MIME type.
- `GET /__bridge_shutdown` (lines 314–323): Loopback-only endpoint (`request.client.host in ("127.0.0.1", "::1", "localhost")`). Sets `self.server.should_exit = True`.
- `GET /api/content_business/status` (lines 121–125): Returns orchestrator status as JSON.
- `POST /api/content_business/action` (lines 126–134): Runs `content_business_control` action and broadcasts `cb_telemetry`.

### 2.5 WebSocket Server (`ws://127.0.0.1:8765/ws`)
- **Origin Validation** (lines 326–328):
  ```python
  if not same_origin_request(ws.headers.get("origin"), ws.headers.get("host")):
      await ws.close(code=1008, reason="Origin check failed")
      return
  ```
  Ensures malicious websites cannot open WebSockets to the local bridge.
- **Client Management** (lines 331–333, 511–513):
  Thread-safe set `self.clients` protected by `self._clients_lock = threading.Lock()`.
- **Initial Connection Handshake** (lines 347–357):
  Immediately sends:
  1. `init`: `{ "type": "init", "assistant_name": ..., "state": ..., "muted": ..., "tts_engine": ..., "tts_voice": ..., "gemini_voice": ..., "edge_voices": ..., "gemini_voices": ... }`
  2. `todo_list`: `{ "type": "todo_list", "tasks": todo_store.list_tasks() }`

### 2.6 Full Message Inventory

#### A. Inbound Messages (Frontend JS -> Python Backend)
| Message Type | Parameters / Payload | Handler in `web_bridge.py` | Action Executed |
|---|---|---|---|
| `todo_add` | `text: str` | Line 372 | Calls `todo_store.add_task(text)`, broadcasts `todo_list` |
| `todo_toggle` | `id: str, completed: bool` | Line 379 | Calls `todo_store.set_completed(id, completed)`, broadcasts `todo_list` |
| `command` | `text: str` | Line 384 | Calls `ui.on_text_command(text)` |
| `interrupt` | *(none)* | Line 388 | Calls `ui.on_interrupt()` |
| `toggle_camera` | *(none)* | Line 391 | Calls `ui.stop_camera_stream()` / `start_camera_stream()` |
| `toggle_mute` | *(none)* | Line 396 | Toggles `ui.muted`, broadcasts `state` |
| `confirm` | `accepted: bool` | Line 404 | Resolves confirmation gate via `confirm_gate.resolve(accepted)` |
| `save_api_key` | `key: str, os: str` | Line 406 | Schedules `ui._win._on_setup_done(key, os)` on Qt thread, logs confirmation |
| `save_voice` | `engine: str, voice: str` | Line 414 | Updates config via `save_tts_engine`/`voice`, triggers `win.on_voice_change()` on Qt thread, broadcasts `voice_updated` |
| `test_voice` | `voice: str` | Line 443 | Speaks test sample asynchronously via `EdgeTTSEngine` in daemon thread |
| `ui_action` | `action: str` | Line 455 | Schedules Qt window actions via `_run_on_qt_thread`: <br>• Overlays: `remote`, `customize`, `audio_devices`, `memory`, `plugins`, `plugin_settings`, `api_setup`<br>• App controls: `shortcut`, `autostart`, `brief`, `wake_toggle`, `wake_manual`, `voice_enroll`, `voice_filter_toggle`, `single_turn_toggle`, `ptt`, `restart`, `fullscreen`, `hide_classic` |

#### B. Outbound Messages (Python Backend -> Frontend JS via `broadcast()`)
| Message Type | Frequency / Trigger | Payload Fields | Frontend Consumer in `ui_improved.html` |
|---|---|---|---|
| `init` | Once on WS connect | `assistant_name`, `state`, `muted`, `tts_engine`, `tts_voice`, `gemini_voice`, `edge_voices`, `gemini_voices` | Sets brand title, audio engine selectors, voice options (lines 1829–1840) |
| `todo_list` | On connect & on change | `tasks: list[dict]` | Renders task cards & task counter (lines 2163–2189) |
| `todo_error` | On task error | `message: str` | Appends system warning message (line 1845) |
| `state` | State/mute change hook | `state: str, muted: bool` | Updates status pill & voice dock active mode (lines 1927–1954) |
| `audio` | Throttled ~25 FPS | `level: float (0.0-1.0)` | Feeds procedural particle orb & wave displacement (lines 1735–1740) |
| `log` | `ui.write_log` hook | `text: str` | Parses `You:` / `SYS:` / `AI:` and appends to chat drawer (lines 1957–1974) |
| `content` | `ui.show_content` hook | `title: str, text: str` | Formats and displays content card in chat history (lines 1868–1870) |
| `confirm_show` | `ui.show_confirm` hook | `title: str, detail: str` | Opens modal dialog `#confirm-backdrop` (lines 1871–1875) |
| `confirm_hide` | `ui.hide_confirm` hook | *(none)* | Closes modal dialog `#confirm-backdrop` (lines 1876–1878) |
| `cam_state` | `_cam_stream_sig` | `active: bool` | Toggles `#cam-pip-card` visibility (lines 1883–1891) |
| `cam_frame` | `_cam_frame_sig` (~15 FPS) | `data: str (base64 JPEG)` | Updates `#cam-pip-img.src` (lines 1892–1896) |
| `voice_updated`| After `save_voice` | `tts_engine`, `tts_voice`, `gemini_voice` | Updates voice selectors & buttons (lines 1829–1840) |
| `cb_telemetry` | On content business run | `data: dict, message: str` | Formats and displays reel/video telemetry (lines 1879–1881) |
| `metrics` | Every 2.0s via `_metrics_pusher` | `cpu: float, mem: float, gpu: float, net: float, disk: float` | Updates HUD System Status card metrics (lines 1856–1867) |

---

## 3. WebEngine Integration Analysis

### 3.1 Integration in `main.py`
In `main.py` (lines 3140–3226):
1. **Bridge Launch** (lines 3143–3151):
   ```python
   from web_bridge import WebUIBridge
   bridge = WebUIBridge(ui)
   bridge.start(open_browser=False)
   ui._win._web_bridge = bridge
   ```
2. **WebEngine Setup** (lines 3171–3221):
   - Initializes `web_window = QWebEngineView()`.
   - Sets background color to opaque black (`QColor(0, 0, 0, 255)`) to eliminate white flashes on GPU compositor repaints.
   - Grants `MediaAudioCapture` permissions automatically:
     ```python
     def handle_permission_request(origin, feature):
         if feature == QWebEnginePage.Feature.MediaAudioCapture:
             web_window.page().setFeaturePermission(
                 origin, feature, QWebEnginePage.PermissionPolicy.PermissionGrantedByUser
             )
     web_window.page().featurePermissionRequested.connect(handle_permission_request)
     ```
   - Retries loading `http://127.0.0.1:8765` up to 10 times with 400ms intervals (`_retry_load`) to handle startup race conditions while Uvicorn binds the port.
   - Once load succeeds (`_on_web_load_finished`), it hides the classic Tk/Qt window (`ui._win.hide()`).
   - If WebEngine initialization raises an exception (e.g. headless environment or missing PyQt6-WebEngine binaries), it gracefully falls back to the classic HUD (`ui._win.show()`).

### 3.2 Architectural Comparison: WebSocket Bridge vs QWebChannel
| Feature | Mark-LV FastAPI/WebSocket Bridge | Standard Qt QWebChannel |
|---|---|---|
| **Mechanism** | Standard WebSocket (`/ws`) via FastAPI/Uvicorn | IPC via `QWebChannel` and `qwebchannel.js` |
| **JS Client API** | Native `new WebSocket(wsUrl)` | Requires `new QWebChannel(qt.webChannelTransport, ...)` |
| **Portability** | Runs in QWebEngine, Chrome, Safari, Edge, mobile browsers | Strictly limited to Qt WebEngine containers |
| **Debugging** | Standard browser DevTools, cURL, Postman, test clients | Requires Qt WebEngine remote debugging port |
| **Security** | CORS regex + same-origin Host/Origin check | Origin isolated within Qt WebEngine process |
| **Testability** | Easily testable headlessly via `fastapi.testclient.TestClient` | Requires full Qt GUI event loop and WebEngine process |

**Architectural Assessment**: Mark-LV's WebSocket bridge is far more modular and testable. The generative UI enhancements should build directly upon this established WebSocket infrastructure.

---

## 4. Generative UI Architecture & Bi-Directional Telemetry

### 4.1 Requirements for Generative UI
According to `ORIGINAL_REQUEST.md` (R2) and `DISPATCH.md`:
1. The HUD interface in `ui_improved.html` must support dynamically rendering interactive dashboard widgets (system status cards, diagnostic telemetry, activity controls).
2. The widgets must render seamlessly alongside the core Three.js visualization without layout displacement or shader performance degradation.
3. The widgets must support bi-directional communication: controls send actions to Python; Python sends live diagnostics, telemetry, and status updates back to the UI.

### 4.2 Proposed Generative UI Protocol
Extend `web_bridge.py` and `ui_improved.html` with three structured message types:

#### 1. Inbound: `widget_action` (JS -> Python)
```json
{
  "type": "widget_action",
  "widget_id": "sys_diagnostics",
  "action": "run_cleanup",
  "payload": { "target": "cache", "deep": false }
}
```
**Backend Handling in `web_bridge.py`**:
```python
elif mtype == "widget_action":
    widget_id = msg.get("widget_id")
    action = msg.get("action")
    payload = msg.get("payload") or {}
    self.handle_widget_action(widget_id, action, payload)
```
Where `handle_widget_action` dispatches to:
- Diagnostic routines (e.g., memory garbage collection, self-repair scans, cache clearing).
- System actions (e.g., process monitoring, network ping tests).
- Content business / Agent workflow triggers.
- Custom registered callbacks on `ui`.

#### 2. Outbound: `widget_render` (Python -> JS)
Allows the backend to dynamically inject an interactive card into the HUD:
```json
{
  "type": "widget_render",
  "widget_id": "sys_diagnostics",
  "title": "DIAGNOSTIC TELEMETRY",
  "category": "system",
  "layout": "telemetry_card",
  "metrics": [
    { "key": "fps", "label": "HUD FPS", "value": "60", "unit": "fps" },
    { "key": "thread_count", "label": "Active Threads", "value": "14", "unit": "" },
    { "key": "self_repair", "label": "Integrity Check", "value": "HEALTHY", "status": "ok" }
  ],
  "controls": [
    { "action": "run_cleanup", "label": "Optimize Memory", "variant": "primary" },
    { "action": "test_ping", "label": "Network Ping", "variant": "secondary" }
  ]
}
```

#### 3. Outbound: `widget_update` (Python -> JS)
High-frequency lightweight updates to existing widgets without re-rendering DOM structure:
```json
{
  "type": "widget_update",
  "widget_id": "sys_diagnostics",
  "metrics": {
    "fps": "59.8",
    "thread_count": "15"
  }
}
```

#### 4. Outbound: `widget_dismiss` (Python -> JS)
```json
{
  "type": "widget_dismiss",
  "widget_id": "sys_diagnostics"
}
```

### 4.3 Frontend Extension Points in `ui_improved.html`
1. **Container Placement**:
   - The left sidebar (`.left-sidebar.interactive`, lines 1303–1419) contains 3 fixed cards.
   - Insert a dynamic container `<div id="generative-widget-dock" class="widget-dock"></div>` in the left sidebar or in a dedicated collapsible HUD overlay.
2. **Visual Consistency**:
   - Style dynamic widgets using the existing Apple visionOS Liquid Glass tokens:
     - `background: var(--glass-surface)`
     - `border: 1px solid var(--glass-border)`
     - `box-shadow: var(--glass-specular)`
     - `border-radius: 20px`
     - Typography: `'Orbitron', sans-serif` for headers, `Inter` for data points.
3. **Z-Index & Performance Safety**:
   - Ensure `pointer-events: auto` on interactive widget cards while preserving `pointer-events: none` on the container layer (`.ui-layer`).
   - Keep Three.js `#webgl-canvas` at `z-index: 1`, interactive cards at `z-index: 10`, and modals at `z-index: 50`.
   - Prevent DOM mutation storms during high-frequency telemetry updates by caching element references by `widget_id` and updating `textContent` in-place.

---

## 5. Existing Pytest Test Suite Audit

### 5.1 Test Execution Baseline
- **Command Executed**: `& C:\jarvis\Mark-LV-main\Mark-LV-main\.venv\Scripts\python.exe -m pytest`
- **Result**:
  ```
  platform win32 -- Python 3.14.8, pytest-9.1.1, pluggy-1.7.0
  rootdir: C:\jarvis\Mark-LV-main\Mark-LV-main
  configfile: pytest.ini
  testpaths: tests
  plugins: anyio-4.15.1
  collected 90 items

  ================== 89 passed, 1 skipped, 1 warning in 7.91s ===================
  ```

### 5.2 Test File Inventory & Coverage Mapping
| Test File | Test Count | Focus Area | Covers UI/Bridge? |
|---|---|---|---|
| `test_agent_integrations.py` | 17 | WhatsApp, YouTube, Agent integrations | ❌ No |
| `test_audio_preprocessor.py` | 3 | Noise suppression, spectral gating | ❌ No |
| `test_coding_workbench.py` | 3 | Tool approvals, workbench callbacks | ❌ No |
| `test_coding_workbench_action.py`| 2 | Code generation and execution | ❌ No |
| `test_coding_workbench_checks.py`| 2 | Syntax, security checks | ❌ No |
| `test_coding_workbench_rollback.py`| 2 | Git/file state rollback | ❌ No |
| `test_content_business.py` | 3 | Orchestrator and task queue | ❌ No |
| `test_gesture_mapper.py` | 3 | Hand gesture to UI command mapping | ❌ No (only maps strings) |
| `test_interaction_routing.py` | 6 | Intent parsing and interaction state | ❌ No |
| `test_passive_actions.py` | 3 | Background suggestions | ❌ No |
| `test_passive_analyzer.py` | 4 | Passive conversation analysis | ❌ No |
| `test_passive_queue.py` | 3 | Action queue priority | ❌ No |
| `test_permission_broker.py` | 4 | Permission broker policies | ❌ No |
| `test_security_hardening.py` | 5 | Safe commands, origin validation | ⚠️ Partial (`same_origin_request` only) |
| `test_self_repair.py` | 8 | AST verification, self repair | ❌ No |
| `test_self_repair_action.py` | 1 | Self repair action dispatcher | ❌ No |
| `test_speaker_id.py` | 5 | Voiceprint recognition | ❌ No |
| `test_task_events.py` | 3 | Event emission for tasks | ❌ No |
| `test_todo_store.py` | 3 | SQLite task storage | ❌ No |
| `test_vad.py` | 4 | Silero VAD energy detection | ❌ No |
| `test_youtu_agent_action.py` | 6 (1 skip)| YouTube data API actions | ❌ No |
| **Total** | **90** | | **0% UI / Bridge Test Coverage** |

### 5.3 Critical Test Gaps
1. **No UI File Resolution Tests**: No tests verify that `web_bridge.py` resolves `ui_improved.html` across source directories, PyInstaller `_MEIPASS`, `_internal`, or bundled executable environments.
2. **No HTTP Endpoint Tests**: No tests verify that `GET /` serves `ui_improved.html` with status 200, or that `GET /three.min.js` serves JavaScript.
3. **No WebSocket Protocol Tests**: No tests verify WebSocket connection establishment, initial `init` and `todo_list` payload delivery, or error handling.
4. **No Inbound Action Tests**: No tests verify that frontend messages (`command`, `interrupt`, `toggle_mute`, `toggle_camera`, `confirm`, `save_voice`, `ui_action`) correctly trigger backend functions or Qt slots.
5. **No Generative UI Tests**: No tests verify dynamic widget creation, updating, action routing, or telemetry push.
6. **No HTML Integrity Tests**: No tests verify that `ui_improved.html` is valid, contains required element IDs, or has valid script/canvas structures.

---

## 6. Recommended Test Suite Architecture

To satisfy Acceptance Criteria ("Quality & Verification: The existing test suite runs and passes with zero regressions; Tests or automated checks verify that the UI initializes and loads the standardized ui_improved.html properly"), we recommend creating a comprehensive test module: `tests/test_web_bridge.py`.

### 6.1 Proposed Test Specifications for `tests/test_web_bridge.py`

#### Group 1: UI File Resolution & Standardization (`TestUIFileResolution`)
- `test_find_ui_file_finds_standardized_html()`:
  - Asserts that `_find_ui_file()` returns a path ending in `ui_improved.html`.
  - Asserts that the returned file exists and is readable.
- `test_find_ui_file_prefers_ui_improved_over_legacy_name()`:
  - Simulates a directory containing both `ui_improved.html` and legacy names; verifies that `ui_improved.html` is selected.
- `test_find_ui_file_supports_frozen_environment()`:
  - Mocks `sys.frozen = True` and `sys._MEIPASS = temp_dir`; verifies resolution.
- `test_find_ui_file_returns_none_when_missing()`:
  - Asserts graceful `(None, candidates)` return when file is absent.

#### Group 2: HTTP Endpoints (`TestWebBridgeHttpRoutes`)
- `test_get_root_serves_ui_improved_html()`:
  - Uses `fastapi.testclient.TestClient`.
  - Asserts HTTP 200, `text/html` media type, and content matching `ui_improved.html`.
- `test_get_root_returns_404_page_when_file_missing()`:
  - Mocks `_find_ui_file` returning `(None, [...])`; asserts HTTP 404 with structured error HTML.
- `test_get_three_js_serves_javascript()`:
  - Asserts HTTP 200 and `application/javascript` media type.
- `test_bridge_shutdown_endpoint_security()`:
  - Asserts HTTP 200 for localhost client IP; asserts HTTP 403 for non-loopback IP.

#### Group 3: WebSocket Connection & Handshake (`TestWebBridgeWebSocket`)
- `test_websocket_rejects_unauthorized_origin()`:
  - Connects with header `Origin: https://malicious.site`; asserts connection rejection (code 1008).
- `test_websocket_accepts_valid_origin()`:
  - Connects with header `Origin: http://127.0.0.1:8765`, `Host: 127.0.0.1:8765`.
  - Asserts connection established.
- `test_websocket_sends_init_and_todo_list_on_connect()`:
  - Asserts receipt of `{"type": "init", ...}` with valid `assistant_name` and `state`.
  - Asserts receipt of `{"type": "todo_list", ...}` with tasks array.

#### Group 4: Inbound WebSocket Messaging & Action Routing (`TestWebBridgeActions`)
- `test_websocket_handles_text_command()`:
  - Sends `{"type": "command", "text": "hello jarvis"}`.
  - Asserts `ui.on_text_command.assert_called_once_with("hello jarvis")`.
- `test_websocket_handles_interrupt()`:
  - Sends `{"type": "interrupt"}`.
  - Asserts `ui.on_interrupt.assert_called_once()`.
- `test_websocket_handles_toggle_mute()`:
  - Sends `{"type": "toggle_mute"}`.
  - Asserts `ui.muted` flips and `state` broadcast is sent.
- `test_websocket_handles_toggle_camera()`:
  - Sends `{"type": "toggle_camera"}`.
  - Asserts camera stream start/stop called.
- `test_websocket_handles_confirm()`:
  - Sends `{"type": "confirm", "accepted": True}`.
  - Asserts `confirm_gate.resolve(True)` called.
- `test_websocket_handles_ui_action()`:
  - Sends `{"type": "ui_action", "action": "fullscreen"}`.
  - Asserts action dispatched onto Qt invoker.

#### Group 5: Generative UI & Widget Communication (`TestGenerativeUIBridge`)
- `test_websocket_handles_widget_action()`:
  - Sends `{"type": "widget_action", "widget_id": "test_widget", "action": "click", "payload": {"foo": "bar"}}`.
  - Asserts widget action handler called with correct arguments.
- `test_broadcast_widget_render_and_update()`:
  - Triggers `bridge.broadcast({"type": "widget_render", ...})`.
  - Asserts connected WebSocket client receives widget descriptor.
- `test_broadcast_telemetry_metrics()`:
  - Triggers `bridge.broadcast({"type": "metrics", ...})`.
  - Asserts client receives telemetry payload with cpu, mem, disk.

#### Group 6: Frontend HTML & DOM Integrity (`TestUIImprovedHtmlIntegrity`)
- `test_ui_improved_html_structure()`:
  - Parses `ui_improved.html` to verify:
    - `<canvas id="webgl-canvas">` exists for Three.js.
    - Script tag for `/three.min.js` exists.
    - Status indicators (`#top-status-dot`, `#online-status-text`) exist.
    - Chat interface (`#chat-history`, `#chat-input`, `#mic-toggle-btn`) exists.
    - System metrics elements (`#cpu-val`, `#gpu-val`, `#ram-val`, `#disk-val`, `#net-val`) exist.
    - Generative widget mounting dock exists.
    - WebSocket connect function `connectBackend()` and handlers exist.

---

## 7. Actionable Implementation Checklist

For downstream planning and implementation tracks:

### R1: Filename Standardization & Packaging
1. [ ] Update `web_bridge.py`:
   - Line 2: Standardize docstring to `ui_improved.html`.
   - Line 52: Standardize function docstring to `ui_improved.html`.
   - Line 82: Prioritize `ui_improved.html` in lookup.
   - Lines 301, 305, 307: Update 404 error strings to `ui_improved.html`.
2. [ ] Update `MarkLV.spec`:
   - Line 44: Remove `('ui improved.html', '.')` and ensure only `('ui_improved.html', '.')` is bundled.
3. [ ] Update `readme.md`:
   - Lines 13 and 36: Standardize `ui improved.html` references to `ui_improved.html`.
4. [ ] Clean up redundant duplicate files in filesystem (`ui improved.html`).

### R2: Generative UI Enhancement
1. [ ] Extend `web_bridge.py`:
   - Add `widget_action` handler in `websocket_endpoint`.
   - Add helper methods `push_widget()`, `update_widget()`, `dismiss_widget()`.
   - Add live diagnostic telemetry broadcast stream.
2. [ ] Extend `ui_improved.html`:
   - Add `#generative-widget-dock` container styled with visionOS Liquid Glass tokens.
   - Add JS widget manager: dynamic rendering of telemetry cards, diagnostic status cards, and action buttons.
   - Wire widget action buttons to `ws.send(JSON.stringify({ type: 'widget_action', ... }))`.
   - Verify Three.js particle orb canvas remains smooth and reactive.

### Quality & Verification
1. [ ] Implement `tests/test_web_bridge.py` covering Groups 1–6 above.
2. [ ] Run full pytest test suite and ensure all 90+ tests pass with 0 regressions.
