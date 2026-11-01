# Handoff Report: WebBridge Bi-Directional Communication & Pytest Test Suite

**Author**: Survey Explorer 3  
**Working Directory**: `C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\teamwork_explorer_survey_3`  
**Recipient**: Orchestrator (`6906300c-9137-4e62-90d0-c438dc9f10d1`)  
**Status**: Hard Handoff (Investigation Complete)  

---

## 1. Observation

1. **Bridge Architecture in `web_bridge.py`**:
   - `web_bridge.py` (lines 20–23, 109): Implements a FastAPI application with WebSocket support (`from fastapi import FastAPI, WebSocket, WebSocketDisconnect`).
   - Line 109: `self.app = FastAPI(title="JARVIS Liquid Glass UI Bridge")`.
   - Line 324: `@self.app.websocket("/ws")` provides bi-directional JSON messaging over WebSocket.
   - Lines 35–48: Thread-safe marshalling to the Qt main thread is implemented via `_QtMainThreadInvoker(QObject)` with `run_callable = pyqtSignal(object)`.
   - Lines 50–88: `_find_ui_file()` checks multiple paths for `("ui_improved.html", "ui improved.html")`.
   - Lines 301, 305, 307: The 404 error response explicitly references `"ui improved.html"` with a space.
   - `web_bridge.py` does **not** use `QWebChannel`.

2. **WebEngine Integration in `main.py`**:
   - `main.py` (lines 5, 3144–3148, 3171–3221):
     ```python
     3145: from web_bridge import WebUIBridge
     3146: bridge = WebUIBridge(ui)
     3147: bridge.start(open_browser=False)
     3148: ui._win._web_bridge = bridge
     ...
     3171: web_window = QWebEngineView()
     ...
     3203: web_window.load(QUrl("http://127.0.0.1:8765"))
     ```
   - Retries loading up to 10 times at 400ms intervals (`_retry_load`, line 3200).
   - Once load succeeds (`_on_web_load_finished`, line 3210), it hides the classic window (`ui._win.hide()`).
   - If WebEngine initialization fails, it catches the exception and falls back to classic HUD (`ui._win.show()`, line 3224).

3. **Packaging References in `MarkLV.spec`**:
   - `MarkLV.spec` (lines 44–45):
     ```python
     44: ('ui improved.html', '.'),
     45: ('ui_improved.html', '.'),
     ```
   - Both filenames are bundled currently.

4. **Frontend Architecture in `ui_improved.html`**:
   - `ui_improved.html` (lines 1805–1912): Connects to `ws://127.0.0.1:8765/ws`.
   - Handled inbound message types: `init`, `todo_list`, `todo_error`, `state`, `audio`, `log`, `metrics`, `content`, `confirm_show`, `confirm_hide`, `cb_telemetry`, `cam_state`, `cam_frame`.
   - Dispatched outbound message types: `toggle_mute`, `confirm`, `interrupt`, `ui_action`, `save_api_key`, `save_voice`, `test_voice`, `todo_toggle`, `todo_add`, `command`, `toggle_camera`.
   - Left sidebar contains 3 hardcoded static cards (`.glass-card`: Today Tasks, System Status, Quick Actions).

5. **Pytest Test Suite Baseline**:
   - Command: `& C:\jarvis\Mark-LV-main\Mark-LV-main\.venv\Scripts\python.exe -m pytest`
   - Result:
     ```
     platform win32 -- Python 3.14.8, pytest-9.1.1, pluggy-1.7.0
     collected 90 items
     89 passed, 1 skipped, 1 warning in 7.91s
     ```
   - `tests/` directory contains 22 files.
   - Exact count of tests covering `web_bridge.py`, `ui.py`, or `ui_improved.html`: **0**.

6. **Headless Verification of `WebUIBridge`**:
   - Successfully executed headless test using `fastapi.testclient.TestClient`:
     - Initialized `WebUIBridge` with a mock Qt UI object and `_QtMainThreadInvoker`.
     - `GET /` returned HTTP 200 with 95,100 bytes of HTML.
     - WebSocket connection to `/ws` successfully performed handshake, received `init` and `todo_list`, and processed incoming `command` messages.

---

## 2. Logic Chain

1. **Premise 1**: The original user request requires standardizing on `ui_improved.html` across all references and equipping it with generative UI capabilities communicating bi-directionally via `web_bridge.py`.
2. **Premise 2**: Observation 1 shows that `web_bridge.py` contains legacy references to `ui improved.html` in its module docstring (line 2), function docstring (line 52), and 404 error HTML messages (lines 301, 305, 307). Observation 3 shows `MarkLV.spec` bundles both files.
3. **Inference 1**: Standardizing on `ui_improved.html` requires modifying `web_bridge.py` (docstrings, search order, error strings), `MarkLV.spec` (removing the spaced filename), and updating `readme.md`.
4. **Premise 3**: Observation 1 and 2 reveal that communication is WebSocket-based over port 8765, where `QWebEngineView` renders the page from the local FastAPI server and interacts with Qt via `_QtMainThreadInvoker`.
5. **Inference 2**: Generative UI widgets do not require introducing `QWebChannel`. They can be integrated into the existing WebSocket protocol by defining declarative widget schemas (`widget_render`, `widget_update`, `widget_action`, `widget_dismiss`), providing a dynamic container in `ui_improved.html`, and routing actions in `web_bridge.py`.
6. **Premise 4**: Observation 5 establishes that while 89 tests pass, there is zero test coverage for the UI, `web_bridge.py`, or `ui_improved.html`.
7. **Premise 5**: Observation 6 proves that `WebUIBridge` and its WebSocket endpoint can be completely, headlessly tested via `fastapi.testclient.TestClient` and mock Qt objects without a browser or GUI display.
8. **Inference 3**: An independent, comprehensive test suite (`tests/test_web_bridge.py`) can be implemented to verify file resolution, HTTP serving, WebSocket bi-directional messaging, and generative UI action handling with zero regressions on existing tests.

---

## 3. Caveats

- **Qt WebEngine Headless Environment**: On headless CI/server environments without a GPU or display server, `QWebEngineView` cannot render visually. However, this is already handled cleanly in `main.py` via exception handling and fallback to classic HUD. Furthermore, all bridge, protocol, and HTML integrity tests can run headlessly via `TestClient`.
- **Port Availability**: `web_bridge.py` uses port 8765 by default. It includes logic to release stale listeners (`_release_stale_listener`), but automated tests should instantiate `WebUIBridge` with `port=0` or test directly against `bridge.app` via `TestClient` to prevent port collision during concurrent test runs.
- **No Other Caveats**: All components were inspected directly in source code and verified with tool commands.

---

## 4. Conclusion

1. **Communication Mechanism**: Mark-LV's bi-directional communication is fully implemented via FastAPI + WebSocket (`ws://127.0.0.1:8765/ws`), with PyQt6 signal marshalling (`_QtMainThreadInvoker`) ensuring thread safety on the Qt main GUI loop.
2. **Generative UI Architecture**: Generative UI should be added natively to `ui_improved.html` and `web_bridge.py` using a structured JSON widget protocol (`widget_render`, `widget_update`, `widget_action`), mounting dynamic cards into a new container (`#generative-widget-dock`) alongside the Three.js particle orb.
3. **Filename Standardization**: Update `web_bridge.py` (lines 2, 52, 82, 301, 305, 307) and `MarkLV.spec` (line 44) to reference only `ui_improved.html`.
4. **Test Suite Addition**: Implement `tests/test_web_bridge.py` covering:
   - UI file resolution across frozen and source paths.
   - HTTP routes (`GET /`, `GET /three.min.js`, `GET /__bridge_shutdown`).
   - WebSocket bi-directional communication and origin security.
   - Generative UI widget action dispatching and telemetry.
   - HTML DOM structure and script tag integrity.

---

## 5. Verification Method

To independently verify the observations and conclusions:

1. **Verify Existing Pytest Suite**:
   ```powershell
   Set-Location C:\jarvis\Mark-LV-main\Mark-LV-main
   & .\.venv\Scripts\python.exe -m pytest
   ```
   *Expected outcome*: 89 passed, 1 skipped, 1 warning.

2. **Verify HTML File Hash & Content Parity**:
   ```powershell
   Set-Location C:\jarvis\Mark-LV-main\Mark-LV-main
   Get-FileHash "ui improved.html", "ui_improved.html"
   ```
   *Expected outcome*: Both return SHA256 `5B3CA8EFFDEECDB8167C9E2E49E42A09C6EDB1783A6F04FC517DC92E11B953B6`.

3. **Verify Headless WebUIBridge Execution**:
   ```powershell
   Set-Location C:\jarvis\Mark-LV-main\Mark-LV-main
   & .\.venv\Scripts\python.exe -c "
   from PyQt6.QtCore import QCoreApplication, QObject, pyqtSignal
   from unittest.mock import MagicMock
   import sys
   app = QCoreApplication.instance() or QCoreApplication(sys.argv)
   class MockWin(QObject):
       _cam_stream_sig = pyqtSignal(bool)
       _cam_frame_sig = pyqtSignal(bytes)
   mock_ui = MagicMock()
   mock_ui.assistant_name = 'JARVIS'
   mock_ui.muted = False
   mock_ui._win = MockWin()
   from web_bridge import WebUIBridge
   bridge = WebUIBridge(mock_ui, port=9999)
   from fastapi.testclient import TestClient
   client = TestClient(bridge.app)
   resp = client.get('/')
   assert resp.status_code == 200
   print('GET / verified: HTTP 200, length:', len(resp.text))
   with client.websocket_connect('/ws', headers={'origin': 'http://127.0.0.1:8765', 'host': '127.0.0.1:8765'}) as ws:
       msg1 = ws.receive_json()
       assert msg1['type'] == 'init'
       print('WS init verified:', msg1['assistant_name'])
   "
   ```
   *Expected outcome*: Prints `GET / verified: HTTP 200` and `WS init verified: JARVIS`.

4. **Invalidation Conditions**:
   - If `web_bridge.py` cannot be instantiated with a mock Qt UI object, headless testing would be invalidated. (Tested: Succeeded).
   - If `fastapi.testclient` were unavailable or incompatible with Python 3.14, async testing would be invalidated. (Tested: Available and compatible).
