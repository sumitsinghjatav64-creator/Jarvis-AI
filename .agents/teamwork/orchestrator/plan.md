# Orchestration Plan: Mark-LV UI Standardization & Generative UI Restoration

## Objective
Standardize on `ui_improved.html` across all references in the Mark-LV application (`main.py`, `ui.py`, `web_bridge.py`, `MarkLV.spec`, etc.) and equip the WebEngine HUD interface in `ui_improved.html` with generative UI capabilities for interactive dashboard widgets, live diagnostics, and modern visual controls communicating bi-directionally via `web_bridge.py`.

## Phases

### Phase 0: Full Codebase Survey (3 Parallel Explorers)
1. **Explorer 1 (HTML Filename Standardization & Launch Paths)**:
   - Identify all HTML file references (`ui.html`, `ui_improved.html`, `ui_restored.html`, or others) in `main.py`, `ui.py`, `web_bridge.py`, `MarkLV.spec`, assets, etc.
   - Trace how HTML files are packaged, located, loaded by PyQt/PySide WebEngine, and verify any 404 or missing file error paths.
2. **Explorer 2 (HUD Visualization & Generative UI Architecture)**:
   - Inspect existing `ui_improved.html` (and any related UI html/js files), Three.js visualizer setup, HUD layout, and container structure.
   - Identify extension points for generative UI: interactive dashboard widgets (system status cards, diagnostic telemetry, activity controls) without disrupting Three.js visualization.
3. **Explorer 3 (WebBridge Bi-directional Communication & Pytest Suite)**:
   - Inspect `web_bridge.py` and JS bridge mechanics (QWebChannel / signals / slots / events).
   - Inspect existing `pytest` test suite, running commands, existing UI tests, and requirements for UI initialization and loading checks.

### Phase 1: PROJECT.md Synthesis & Architecture Specification
- Synthesize the 3 Explorer reports into `PROJECT.md` with:
  - Architecture overview & data flow
  - Complete Feature Inventory
  - Milestone decomposition with explicit dependencies
  - Interface contracts (WebBridge <-> Frontend Generative UI)
  - Code layout & ownership

### Phase 2: Dual Track Execution
- **Implementation Track**:
  - Milestone 1: Filename Standardization & Packaging Fixes
  - Milestone 2: Generative UI Framework & Interactive Widgets in `ui_improved.html`
  - Milestone 3: Bi-directional WebBridge Communication & Telemetry/Control Handlers
- **E2E Testing Track**:
  - Independent requirement-driven test harness and test suites (Tiers 1-4)
  - Publish `TEST_READY.md`

### Phase 3: Final Integration, E2E Test Suite Pass & Adversarial Hardening
- Run full pytest and E2E verification
- Phase 1: 100% test pass
- Phase 2: Adversarial coverage hardening (Tier 5)

### Phase 4: Final Verification & Reporting
- Final review and forensic integrity audit
- Report results to caller/sentinel
