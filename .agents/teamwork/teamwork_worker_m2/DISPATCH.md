# Task Assignment: Milestone 2 Worker (Generative UI Implementation in ui_improved.html)

- **Role**: teamwork_worker
- **Working Directory**: C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\teamwork_worker_m2
- **Project Root**: C:\jarvis\Mark-LV-main\Mark-LV-main
- **Original Request**: C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\ORIGINAL_REQUEST.md
- **Project Specification**: C:\jarvis\Mark-LV-main\Mark-LV-main\PROJECT.md
- **Explorer 1 Handoff (DOM & CSS)**: C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\teamwork_explorer_m2_1\handoff.md
- **Explorer 1 Survey Report**: C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\teamwork_explorer_m2_1\survey_report.md
- **Explorer 2 Handoff (WidgetManager)**: C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\teamwork_explorer_m2_2\handoff.md
- **Explorer 2 Survey Report**: C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\teamwork_explorer_m2_2\survey_report.md
- **Explorer 3 Handoff (Templates & WS Routing)**: C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\teamwork_explorer_m2_3\handoff.md
- **Explorer 3 Survey Report**: C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\teamwork_explorer_m2_3\survey_report.md

## Exclusive File Ownership
You exclusively own:
- `C:\jarvis\Mark-LV-main\Mark-LV-main\ui_improved.html`

## Implementation Tasks
Integrate the Generative UI framework into `ui_improved.html` using the exact blueprints provided by Explorers 1, 2, and 3:

1. **DOM Container Placement**:
   - Insert `<div class="gen-ui-dock interactive" id="gen-ui-dock" aria-live="polite"></div>` inside `.ui-layer` at line 1427 (immediately following the `.right-hud` closing tag).
2. **CSS Styling Insertion**:
   - Insert the complete, compositor-safe Generative UI styles before line 1245 (`</style>`):
     - Container styles (`#gen-ui-dock`, `.gen-ui-dock.cam-offset`)
     - Card styles (`.gen-ui-card`, `.gen-ui-header`, `.gen-ui-metrics-grid`, `.gen-ui-metric-card`, `.gen-ui-gauge-card`, `.gen-ui-progress-track`, `.gen-ui-btn`, `.gen-ui-btn-grid`, `.gen-ui-tile-grid`, `.gen-ui-tile`)
     - Inline chat bubble styles (`.chat-bubble.gen-ui-bubble`)
     - Keyframe animations (`genUiCardEnter`, `.dismissing`)
     - Note: Strictly avoid `backdrop-filter: blur(...)` to prevent WebEngine GPU rasterization stalls.
3. **JavaScript Engine & Templates Insertion**:
   - In `<script>` (around line 1800, before WebSocket connection):
     - Insert `WidgetTemplates` with offline SVG vector icon table, template generators (`telemetry`, `activity_tracker`, `action_grid`, `custom`), and targeted delta updater methods.
     - Insert `WidgetManager` class with lifecycle methods (`renderWidget`, `updateWidget`, `dismissWidget`, `clearAll`), $O(1)$ element caching, animation coordination, and leak-free teardown (`_teardownEntry`).
     - Instantiate global `window.widgetManager = new WidgetManager();`.
4. **WebSocket Inbound Routing & Outbound Action Dispatching**:
   - In `ws.onmessage` at line 1882 (`// === PUT THEM RIGHT HERE ===`), add handlers for:
     - `widget_render`: `if (window.widgetManager) window.widgetManager.renderWidget(msg.widget);`
     - `widget_update`: `if (window.widgetManager) window.widgetManager.updateWidget(msg.widget_id, msg.data);`
     - `widget_dismiss`: `if (window.widgetManager) window.widgetManager.dismissWidget(msg.widget_id);`
   - In camera state handler (`msg.type === 'cam_state'`), toggle `.cam-offset` on `#gen-ui-dock`.
   - Implement `sendWidgetAction(widgetId, actionId, payload)` and document-level delegated click listener on `[data-action-id]` that plays `sfx.click()` and sends `{ type: 'widget_action', widget_id, action_id, payload }` via `ws.send()`.
5. **Testing & Verification**:
   - Run `python -m pytest tests/test_ui_standardization.py tests/test_web_bridge_e2e.py -v`.
   - Run full regression suite `python -m pytest`.
   - Verify `ui_improved.html` decodes as valid UTF-8 and loads properly.

## MANDATORY INTEGRITY WARNING
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

When finished, produce `handoff.md` and `progress.md` in your working directory and notify the orchestrator (recipient: 6906300c-9137-4e62-90d0-c438dc9f10d1).


## 2026-10-31T08:42:34Z
You are Milestone 2 Worker.
Read ORIGINAL_REQUEST.md at: C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\ORIGINAL_REQUEST.md
Read PROJECT.md at: C:\jarvis\Mark-LV-main\Mark-LV-main\PROJECT.md
Read DISPATCH.md at: C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\teamwork_worker_m2\DISPATCH.md
Your working directory is: C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\teamwork_worker_m2

Review the survey reports and handoffs from Explorer 1, Explorer 2, and Explorer 3:
- Explorer 1 (DOM & CSS Layout): C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\teamwork_explorer_m2_1\survey_report.md
- Explorer 2 (WidgetManager Lifecycle): C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\teamwork_explorer_m2_2\survey_report.md
- Explorer 3 (Templates & WS Routing): C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\teamwork_explorer_m2_3\survey_report.md

Exclusive File Ownership:
- C:\jarvis\Mark-LV-main\Mark-LV-main\ui_improved.html

Execute the tasks:
1. Insert the #gen-ui-dock DOM container into .ui-layer at line 1427.
2. Insert the complete Generative UI CSS styling rules before </style> at line 1245.
3. Insert WidgetTemplates (templates, updater functions, inline SVG icon table) and the WidgetManager class before WebSocket initialization (~line 1800) and expose window.widgetManager.
4. Add inbound WebSocket routing for widget_render, widget_update, widget_dismiss at line 1882, handle cam_state offset, and add outbound sendWidgetAction event delegation.
5. Run tests (pytest tests/test_ui_standardization.py tests/test_web_bridge_e2e.py and full pytest suite) to verify zero regressions.
