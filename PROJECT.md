# Project: Mark-LV UI Standardization & Generative UI Restoration

## Architecture
Mark-LV is an autonomous voice assistant featuring a PyQt6 desktop shell that embeds a modern Liquid Glass web interface rendered via `QWebEngineView`.
- **Backend Bridge (`web_bridge.py`)**: A local FastAPI + Uvicorn server running on `http://127.0.0.1:8765` providing HTTP asset serving and a real-time WebSocket endpoint (`/ws`). Qt thread safety is managed via `_QtMainThreadInvoker(QObject)`.
- **Frontend HUD (`ui_improved.html`)**: A Three.js 3D WebGL particle orb and feathered ribbon visualization overlaid with a Liquid Glass HUD (`.ui-layer`). Compositor-safe CSS avoids runtime rasterization stutters.
- **Generative UI Framework**: A dynamic widget container (`#gen-ui-dock` and in-line `.gen-ui-bubble`) managed by a JavaScript `WidgetManager` that dynamically instantiates, updates, and dismisses interactive dashboard controls, live diagnostics, and telemetry cards.
- **Bi-Directional Communication Flow**:
  - Backend -> Frontend: Server pushes `widget_render`, `widget_update`, `widget_dismiss`, and telemetry data over `/ws`.
  - Frontend -> Backend: User actions on widgets emit `widget_action` messages over `/ws`, handled and dispatched safely to Qt assistant methods.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Standardize HTML Filename References in `web_bridge.py` | Update docstrings (lines 2, 52), candidate search list (line 82), and 404 missing-file error responses (lines 301, 305, 307) to use `ui_improved.html`. | M1 | Survey 1, Survey 3, R1 |
| 2 | Standardize PyInstaller Data Bundling in `MarkLV.spec` | Remove duplicate `('ui improved.html', '.')` and ensure canonical `('ui_improved.html', '.')` is bundled. | M1 | Survey 1, R1 |
| 3 | Documentation & Git Tracking Alignment | Update references in `readme.md`; ensure `ui_improved.html` is properly tracked and `ui improved.html` is removed. | M1 | Survey 1 |
| 4 | Generative UI DOM Container & Glass Tokens | Add `#gen-ui-dock` container (right-side dock) and `.gen-ui-bubble` styles using compositor-safe liquid glass tokens without obstructing Three.js canvas. | M2 | Survey 2, R2 |
| 5 | Dynamic `WidgetManager` Lifecycle Engine | Pure-JS manager in `ui_improved.html` supporting `renderWidget(schema)`, `updateWidget(id, data)`, and `dismissWidget(id)`. | M2 | Survey 2, R2 |
| 6 | Interactive Widget Templates | Built-in schemas & templates for system status cards, diagnostic telemetry, and activity/action controls. | M2 | Survey 2, R2 |
| 7 | Inbound `widget_action` WebSocket Handler | Extend `web_bridge.py` WebSocket loop to parse and handle `widget_action` messages from frontend widgets. | M3 | Survey 3, R2 |
| 8 | Backend Widget Dispatch & Telemetry Helpers | Methods on `WebUIBridge` (`render_widget`, `update_widget`, `dismiss_widget`, and telemetry broadcasts) thread-safely invokable from Qt/Jarvis. | M3 | Survey 3, R2 |
| 9 | Comprehensive E2E Test Suite | Requirement-driven opaque-box tests covering Tiers 1-4 (HTML serving, 404 handling, WebSocket lifecycle, widget actions, regressions). | E2E Track | Survey 1, Survey 3 |
| 10 | Final E2E Test Pass & Adversarial Hardening | Verify 100% pass rate across Tiers 1-4 and execute white-box adversarial testing (Tier 5). | M4 | Project Pattern |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | UI Filename Standardization & Packaging | Standardize references in `web_bridge.py`, `MarkLV.spec`, `readme.md`, and Git tracking. | None | DONE |
| M2 | Generative UI Framework in `ui_improved.html` | Implement `#gen-ui-dock`, CSS styling, `WidgetManager`, and interactive widget templates. | M1 | IN_PROGRESS |
| M3 | Bi-directional WebBridge Communication | Implement `widget_action` handling and backend widget dispatch helpers in `web_bridge.py`. | M2 | PLANNED |
| M4 | Final Milestone (E2E Test Pass & Adversarial Hardening) | Phase 1: Pass 100% of E2E tests (Tiers 1-4). Phase 2: Adversarial coverage hardening (Tier 5). | M1, M2, M3, E2E Track | PLANNED |

## Interface Contracts

### Frontend Generative UI ↔ Backend `web_bridge.py`

#### Server-to-Client Messages (via WebSocket `/ws`)
1. **`widget_render`**:
   ```json
   {
     "type": "widget_render",
     "widget": {
       "id": "diag_sys_status",
       "template": "telemetry" | "activity_tracker" | "action_grid" | "custom",
       "title": "System Diagnostics",
       "icon": "cpu",
       "target": "dock" | "chat",
       "data": { ... },
       "actions": [
         { "action_id": "refresh", "label": "Refresh", "variant": "primary" }
       ]
     }
   }
   ```
2. **`widget_update`**:
   ```json
   {
     "type": "widget_update",
     "widget_id": "diag_sys_status",
     "data": { ... }
   }
   ```
3. **`widget_dismiss`**:
   ```json
   {
     "type": "widget_dismiss",
     "widget_id": "diag_sys_status"
   }
   ```

#### Client-to-Server Messages (via WebSocket `/ws`)
1. **`widget_action`**:
   ```json
   {
     "type": "widget_action",
     "widget_id": "diag_sys_status",
     "action_id": "refresh",
     "payload": { ... }
   }
   ```

## Code Layout
- Frontend UI: `ui_improved.html` (owns HTML structure, CSS styling, Three.js 3D canvas, HUD, `WidgetManager`)
- Web Bridge: `web_bridge.py` (owns FastAPI server, static file resolution `_find_ui_file`, WebSocket `/ws` loop, Qt main thread invoker)
- Packaging Spec: `MarkLV.spec` (owns PyInstaller bundle data mappings)
- Tests: `tests/test_web_bridge.py` and `tests/test_ui_standardization.py` (owned by E2E Testing Track)
- App Integration: `main.py` (loads `http://127.0.0.1:8765` into `QWebEngineView`)
