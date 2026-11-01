# Original User Request

## Approved Task Prompt — 2026-10-31T07:16:50Z

Standardize and restore the Mark-LV application UI by standardizing on `ui_improved.html` across all references and equipping it with generative UI capabilities for interactive dashboard widgets and controls.

Working directory: C:\jarvis\Mark-LV-main\Mark-LV-main
Integrity mode: development

## Requirements

### R1. UI Visibility and HTML Filename Standardization
Standardize on a single consistent HTML filename (`ui_improved.html`) and update all references across the codebase (including `main.py`, `ui.py`, `web_bridge.py`, and `MarkLV.spec`) so that the application UI launches and displays reliably without missing file or runtime loading errors.

### R2. Generative UI Enhancement
Equip the WebEngine HUD interface in `ui_improved.html` with generative UI capabilities to dynamically render interactive dashboard widgets, live diagnostics, and modern visual controls alongside the core Three.js visualization, communicating bi-directionally via `web_bridge.py`.

## Acceptance Criteria

### UI Standardization & Visibility
- [ ] All references across the codebase to the improved UI HTML file use the standardized filename `ui_improved.html`.
- [ ] The application UI launches successfully and renders the web interface without missing file or HTTP 404 / resource loading errors.

### Generative UI & Dashboard Controls
- [ ] `ui_improved.html` supports rendering dynamic, interactive UI widgets (such as system status cards, diagnostic telemetry, or activity controls) alongside the core visualization.
- [ ] Generative UI controls communicate bi-directionally with the backend through `web_bridge.py`.

### Quality & Verification
- [ ] The existing test suite (`pytest`) runs and passes with zero regressions.
- [ ] Tests or automated checks verify that the UI initializes and loads the standardized `ui_improved.html` properly.
