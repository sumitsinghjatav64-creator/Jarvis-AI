# TEST_INFRA — Mark-LV Test Infrastructure Specification

## 1. Test Philosophy: Opaque-Box, Requirement-Driven Testing

The Mark-LV UI Standardization and Generative UI restoration test suite follows an opaque-box, requirement-driven methodology. Tests are constructed from external system specifications (`ORIGINAL_REQUEST.md` and `PROJECT.md`), exercising observable boundaries rather than private implementation details.

### Core Principles
1. **Opaque-Box Boundary Verification**: Test through public HTTP endpoints, WebSocket protocols, CLI/spec artifacts, and public Qt interface contracts.
2. **Deterministic Expected Outputs**: Expected outputs are derived directly from specification contracts (HTTP status codes, WebSocket message schemas, MIME types, and error structures).
3. **Progressive Testability & Isolation**: Tests are self-contained, set up their own mock state, execute independently of execution order, and leave zero persistent side effects.
4. **Zero Regressions Baseline**: All new tests augment the existing 89 passing unit tests without regressions.

---

## 2. Feature Inventory Coverage Mapping

| Feature # | Feature Description | Milestone | Covered By Test Suite | Test Tiers |
|---|---|---|---|---|
| F1 | Standardize HTML Filename References in `web_bridge.py` | M1 | `test_ui_standardization.py` | Tier 1, Tier 2 |
| F2 | Standardize PyInstaller Data Bundling in `MarkLV.spec` | M1 | `test_ui_standardization.py` | Tier 1 |
| F3 | Documentation & Git Tracking Alignment | M1 | `test_ui_standardization.py` | Tier 1 |
| F4 | Generative UI DOM Container & Glass Tokens | M2 | `test_ui_standardization.py`, `test_web_bridge_e2e.py` | Tier 1, Tier 3 |
| F5 | Dynamic `WidgetManager` Lifecycle Engine | M2 | `test_web_bridge_e2e.py` | Tier 1, Tier 3 |
| F6 | Interactive Widget Templates | M2 | `test_web_bridge_e2e.py` | Tier 1, Tier 4 |
| F7 | Inbound `widget_action` WebSocket Handler | M3 | `test_web_bridge_e2e.py` | Tier 1, Tier 2, Tier 3 |
| F8 | Backend Widget Dispatch & Telemetry Helpers | M3 | `test_web_bridge_e2e.py` | Tier 1, Tier 3, Tier 4 |
| F9 | Comprehensive E2E Test Suite | E2E Track | `test_ui_standardization.py`, `test_web_bridge_e2e.py` | Tiers 1–4 |
| F10 | Final E2E Test Pass & Adversarial Hardening | M4 | Full suite + adversarial tests | Tiers 1–5 |

---

## 3. Test Architecture

### 3.1 Test Runner & Environment
- **Test Framework**: `pytest` (v9.1.1+)
- **Async & HTTP Harness**: `fastapi.testclient.TestClient` (Starlette ASGI TestClient)
- **Qt GUI Simulation**: Headless `PyQt6` `QApplication` instance with mock `QObject` signal dispatchers (`_cam_stream_sig`, `_cam_frame_sig`, `_QtMainThreadInvoker`).
- **Execution Command**:
  ```powershell
  Set-Location C:\jarvis\Mark-LV-main\Mark-LV-main
  & ".\.venv\Scripts\python.exe" -m pytest tests/test_ui_standardization.py tests/test_web_bridge_e2e.py -v
  ```
- **Full Suite Run Command**:
  ```powershell
  Set-Location C:\jarvis\Mark-LV-main\Mark-LV-main
  & ".\.venv\Scripts\python.exe" -m pytest -v
  ```

### 3.2 Directory Layout
```
C:\jarvis\Mark-LV-main\Mark-LV-main\
├── tests\
│   ├── test_ui_standardization.py       # Tiers 1 & 2: Filename, static serving, 404, spec validation
│   ├── test_web_bridge_e2e.py           # Tiers 1-4: WebSocket lifecycle, security, gen-UI, E2E flows
│   ├── test_agent_integrations.py       # Pre-existing test suite
│   ├── ...                              # Pre-existing test files (22 total)
│   └── __init__.py
├── web_bridge.py                        # FastAPI + WebSocket backend bridge
├── ui_improved.html                     # Three.js WebGL particle orb & Liquid Glass HUD
├── MarkLV.spec                          # PyInstaller packaging specification
├── TEST_INFRA.md                        # Test architecture specification (this file)
└── TEST_READY.md                        # Test readiness and verification summary
```

---

## 4. Four-Tier Testing Methodology

### Tier 1: Feature Coverage (>=5 tests per core feature)
Verifies nominal, primary happy-path behavior across all exposed interfaces:
1. `_find_ui_file()` accurately resolves `ui_improved.html` from repository root and candidate paths.
2. `GET /` serves `ui_improved.html` with HTTP status 200 and Content-Type `text/html; charset=utf-8`.
3. `GET /three.min.js` serves local script asset with HTTP status 200 and Content-Type `application/javascript`.
4. WebSocket `/ws` handshake succeeds, transmitting initial `init` (configuration, assistant state, voice catalog) and `todo_list` messages.
5. Inbound WebSocket actions (`command`, `interrupt`, `toggle_mute`, `toggle_camera`, `confirm`) dispatch to backend UI methods without error.
6. Spec file bundling verification: `MarkLV.spec` includes canonical `('ui_improved.html', '.')`.

### Tier 2: Boundary & Corner Cases (>=5 tests per core feature)
Examines system resilience against abnormal, missing, or malformed inputs:
1. **Missing UI File Fallback**: When `_find_ui_file()` returns `None`, `GET /` responds with HTTP 404 and HTML containing diagnostic missing file guidance.
2. **Origin Header Validation**: Unauthorized browser origins (e.g., `http://evil.com`) are rejected with WebSocket close code 1008 ("Origin check failed").
3. **Malformed JSON Handling**: Corrupted or non-JSON WebSocket payloads (empty, invalid syntax, non-dict JSON primitives) are caught and logged without dropping the connection or crashing the server loop.
4. **Unknown Message Types & Actions**: Unexpected message types and unrecognized `ui_action` or `widget_action` identifiers are handled gracefully without exceptions.
5. **Extreme & Boundary Payloads**: Large text commands (64KB), empty strings, and special character edge cases are handled without buffer overflow or serialization errors.

### Tier 3: Cross-Feature Combinations (Pairwise Interaction)
Validates interactions between asynchronous subsystems:
1. **Audio Level Streaming & Action Dispatching**: High-frequency audio level updates (throttled at ~25 FPS) execute concurrently with inbound user commands and confirmation prompts.
2. **Concurrent WebSocket Connections**: Multiple simultaneous clients receive broadcast state updates; disconnected or dropped clients are pruned without affecting surviving connections.
3. **Settings, Voice Updates & State Interleaving**: Simultaneous `save_voice`, `toggle_mute`, and `todo_add` calls process cleanly across the Qt thread invoker.
4. **Generative UI Protocol Interleaving**: Bi-directional widget lifecycles (`widget_render`, `widget_update`, `widget_dismiss`) adhere to JSON interface contracts while background metrics push is active.

### Tier 4: Real-World Application Scenarios (>=5 Scenarios)
Exercises end-to-end user workflows matching actual runtime conditions:
1. **Scenario 1 — Complete Application Startup & HUD Readiness**:
   Assistant launches -> `WebUIBridge` initializes -> WebEngine requests `GET /` -> Three.js loaded via `GET /three.min.js` -> WebSocket handshake completes -> Initial `init` and `todo_list` received -> UI transitions to active listening.
2. **Scenario 2 — Live Assistant Command & Telemetry Feedback**:
   Client sends natural language text command -> Backend registers command -> Log message and state change broadcast -> Client receives real-time updates.
3. **Scenario 3 — Generative UI System Diagnostics Lifecycle**:
   Backend triggers diagnostic widget render -> Frontend renders system status card -> User clicks "refresh" widget action -> Backend invoker processes action -> Backend pushes widget update with refreshed metrics.
4. **Scenario 4 — Rapid WebEngine Reload / Reconnection Handling**:
   Simulates rapid tab reload or WebEngine retry attempts (5 sequential reconnects). Validates that connection pools do not leak sockets or accumulate ghost subscribers.
5. **Scenario 5 — Companion Dashboard & Web Bridge Coexistence**:
   Companion mobile server API endpoints (`/api/content_business/status` and `/api/content_business/action`) operate in harmony with main HUD WebSocket and static asset routes without crosstalk.

---

## 5. Coverage Thresholds & Quality Metrics

| Tier | Category | Minimum Required | Target Coverage |
|---|---|---|---|
| Tier 1 | Feature Coverage | >= 5 per feature | 100% of nominal feature workflows |
| Tier 2 | Boundary & Corner Cases | >= 5 per feature | All input boundaries, error codes, security checks |
| Tier 3 | Cross-Feature Combinations | Pairwise coverage | All concurrent and asynchronous subsystems |
| Tier 4 | Real-World Application Scenarios | >= 5 scenarios | 5 end-to-end user workflows |
| Baseline | Regression Prevention | 0 regressions | 100% pass on pre-existing 89 tests |
