# Task Assignment: E2E Testing Track (Test Suite Author)

- **Role**: teamwork_test_writer
- **Working Directory**: C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\teamwork_test_writer_e2e
- **Project Root**: C:\jarvis\Mark-LV-main\Mark-LV-main
- **Original Request**: C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\ORIGINAL_REQUEST.md
- **Project Specification**: C:\jarvis\Mark-LV-main\Mark-LV-main\PROJECT.md

## Objectives & Deliverables
You own the independent, requirement-driven E2E Testing Track for the Mark-LV UI Standardization and Generative UI restoration.

1. **Create `TEST_INFRA.md` at project root (`C:\jarvis\Mark-LV-main\Mark-LV-main\TEST_INFRA.md`)**:
   Follow the template from the project instructions:
   - Test Philosophy: Opaque-box, requirement-driven.
   - Feature Inventory coverage mapping.
   - Test Architecture (test runner command, format, directory layout).
   - Real-World Application Scenarios (Tier 4).
   - Coverage thresholds (Tier 1 >=5/feat, Tier 2 >=5/feat, Tier 3 pairwise, Tier 4 >=5 real-world).

2. **Implement the Comprehensive Test Suite**:
   Write independent, robust tests in `tests/test_ui_standardization.py` and `tests/test_web_bridge_e2e.py` using `pytest` and `fastapi.testclient.TestClient` with mock Qt UI objects:
   - **Tier 1 (Feature Coverage)**:
     - Verify `ui_improved.html` is resolved by `_find_ui_file()`.
     - Verify `GET /` serves `ui_improved.html` with HTTP 200 and correct Content-Type.
     - Verify `GET /three.min.js` serves local script.
     - Verify WebSocket `/ws` handshake and initial `init` and `todo_list` messages.
     - Verify no references to `ui improved.html` remain in source or spec files.
   - **Tier 2 (Boundary & Corner Cases)**:
     - Missing UI file fallback: verify HTTP 404 response mentions `ui_improved.html` when file is missing.
     - Origin header validation: verify unauthorized origins are rejected and valid origins accepted.
     - Malformed JSON sent over WebSocket handled gracefully without server crash.
     - Unknown widget action handling.
     - Large payload / boundary values in widget state.
   - **Tier 3 (Cross-Feature Combinations)**:
     - Dynamic `widget_action` dispatching to backend invoker while streaming audio levels.
     - Concurrent WebSocket connections.
     - Settings, camera toggle, and generative UI action interleaving.
   - **Tier 4 (Real-World Application Scenarios)**:
     - Full application lifecycle: Assistant startup -> WebEngine loads `ui_improved.html` -> WebSocket establishes connection -> System status widget rendered -> User clicks action -> Telemetry updates received.
     - Companion dashboard coexistence without interference.

3. **Verify All Tests Pass**:
   Run `pytest` to verify the existing 89 tests plus all new tests pass with 0 regressions.

4. **Publish `TEST_READY.md` at project root (`C:\jarvis\Mark-LV-main\Mark-LV-main\TEST_READY.md`)**:
   Include test runner command, coverage summary table by tier, and feature checklist.

Deliver your `handoff.md` and report back when `TEST_READY.md` is published.


## 2026-10-31T07:35:09Z
You are the E2E Test Writer for the independent E2E Testing Track.
Read ORIGINAL_REQUEST.md at: C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\ORIGINAL_REQUEST.md
Read PROJECT.md at: C:\jarvis\Mark-LV-main\Mark-LV-main\PROJECT.md
Read your DISPATCH.md at: C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\teamwork_test_writer_e2e\DISPATCH.md
Your working directory is: C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\teamwork_test_writer_e2e

Deliverables:
1. Create TEST_INFRA.md at project root (C:\jarvis\Mark-LV-main\Mark-LV-main\TEST_INFRA.md) using the 4-tier methodology.
2. Implement comprehensive tests in tests/ (e.g. tests/test_ui_standardization.py, tests/test_web_bridge_e2e.py) using pytest and TestClient with mock Qt UI objects.
3. Verify test execution via pytest (confirm all pass with 0 regressions).
4. Publish TEST_READY.md at project root (C:\jarvis\Mark-LV-main\Mark-LV-main\TEST_READY.md).
5. Write your handoff.md in your working directory and notify the orchestrator (recipient: 6906300c-9137-4e62-90d0-c438dc9f10d1).
