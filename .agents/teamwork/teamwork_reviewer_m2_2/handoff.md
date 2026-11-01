# Milestone 2 Reviewer 2: Adversarial & Quality Review Report

- **Reviewer**: Milestone 2 Reviewer 2 (`teamwork_reviewer_m2_2`)
- **Roles**: reviewer, critic
- **Target File**: `C:\jarvis\Mark-LV-main\Mark-LV-main\ui_improved.html`
- **Working Directory**: `C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\teamwork_reviewer_m2_2`
- **Recipient**: Orchestrator (`6906300c-9137-4e62-90d0-c438dc9f10d1`)
- **Date**: 2026-10-31
- **Verdict**: **`REQUEST_CHANGES`**

---

## 1. Observation

1. **Pytest Test Suites Execution**:
   - Running newly authored UI standardization and E2E suites:
     ```powershell
     Set-Location C:\jarvis\Mark-LV-main\Mark-LV-main
     .\.venv\Scripts\python.exe -m pytest tests/test_ui_standardization.py tests/test_web_bridge_e2e.py -v
     ```
     Result: **37 passed, 1 warning in 1.99s**.
   - Running full project regression suite:
     ```powershell
     Set-Location C:\jarvis\Mark-LV-main\Mark-LV-main
     .\.venv\Scripts\python.exe -m pytest
     ```
     Result: **139 passed, 1 skipped, 2 warnings in 12.71s** (0 failures).

2. **Integrity & Anti-Cheat Audit**:
   - `git diff --stat ui_improved.html` shows 1,529 additions and 1 deletion strictly contained within `ui_improved.html`.
   - No test assertions or expected outputs were hardcoded in `ui_improved.html`.
   - The implementation is comprehensive and non-trivial: 17 inline SVGs, 4 built-in template generators, 4 delta updaters, full `WidgetManager` lifecycle engine, inbound WebSocket routing, outbound action dispatcher, and complete compositor-safe CSS styling.
   - Zero facade or shortcut patterns detected.

3. **DOM Structure, Three.js Clearance, and CSS Compositor Safety**:
   - Three.js canvas `#webgl-canvas` is placed at `z-index: 1`, covering the viewport (`position: absolute; top: 0; left: 0; width: 100%; height: 100%`).
   - `.ui-layer` is configured with `pointer-events: none;`, overlaying at `z-index: 10`. Pointer interactions in the center pass directly to the WebGL canvas.
   - `#gen-ui-dock` is mounted at `right: 34px; top: 258px; bottom: 130px; width: 304px; z-index: 25; pointer-events: auto;`. Symmetrically opposite `.left-sidebar` (`width: 304px` at `left: 34px`), leaving 1244px of horizontal center space completely unobstructed.
   - When Camera PiP opens, `.cam-offset` shifts `#gen-ui-dock` to `top: 524px` smoothly via `transition: top 0.32s var(--spring);`.
   - Confirmed absence of `backdrop-filter: blur(...)` across the entire `ui_improved.html` file, avoiding WebGL canvas read-back rasterization stalls in Qt WebEngine.

4. **Event Unbinding and Memory Safety**:
   - Outbound actions and widget dismissal are handled via a single document-level delegated listener at line 3741 (`document.addEventListener('click', ...)`). No per-card closures or event listeners are bound to individual buttons or card elements.
   - `_teardownEntry(entry)` unbinds any tracked listeners, removes `containerEl` from its parent DOM node, clears `entry.elements` map, deletes `entry.id` from `this.widgets`, and explicitly nullifies all entity fields (`containerEl = null; schema = null; data = null; elements = null; listeners = null`).
   - Auto-dismiss timers (`ttl_ms` / `auto_dismiss_ms`) are cancelled via `clearTimeout` when widgets are dismissed.

5. **DOM Injection & Attribute Breakout Vectors (Adversarial PoC)**:
   - In `ui_improved.html` lines 2553 and 2569:
     ```javascript
     <div class="gen-metric-row" data-metric-id="${m.id || m.label}">
     <div class="gen-metric-row" data-metric-id="${k}">
     ```
     `m.id || m.label` and `k` are interpolated directly without `this._escape(...)`.
     When passed `label: 'metric"><img src=x onerror=alert(1)>'`, the resulting HTML output is:
     ```html
     <div class="gen-metric-row" data-metric-id="metric"><img src=x onerror=alert(1)>">
     ```
     This injects a live `<img>` tag with executing `onerror` into the DOM via `cardEl.innerHTML = htmlContent`.
   - In `ui_improved.html` line 2594:
     ```javascript
     <span class="gen-gauge-val">${gVal}</span>
     ```
     `gVal = data.gauge.value || 0;` is interpolated without escaping. If `data.gauge.value` is an HTML string, it renders raw HTML.
   - In `ui_improved.html` lines 2530 & 2533:
     ```javascript
     const variant = act.variant || '';
     <button class="gen-ui-btn ${variant}" ...>
     ```
     `variant` is interpolated raw into the class attribute. If `variant` contains double quotes, e.g. `primary" onfocus="alert(3)`, it breaks out into an attribute injection.
   - In `ui_improved.html` line 2701:
     ```javascript
     <span class="gen-tracker-state-badge status-${statusText.toLowerCase()}" data-bind="status">${this._escape(statusText)}</span>
     ```
     `statusText` is sanitized for the inner text via `this._escape`, but interpolated directly into `status-${statusText.toLowerCase()}` in the class attribute without sanitization.

6. **FIFO Dock Eviction Failure During Bursts**:
   - In `ui_improved.html` lines 2873-2879:
     ```javascript
     if (target === 'dock') {
       const dockEntries = Array.from(this.widgets.values()).filter(e => e.target === 'dock');
       if (dockEntries.length >= this.maxDockWidgets) {
         const oldest = dockEntries[0];
         this.dismissWidget(oldest.id, { immediate: false });
       }
     }
     ```
   - When 8 widgets are pushed in rapid succession (simulating backend broadcast burst), `dismissWidget(oldest.id, { immediate: false })` starts a 380ms transition. The entry remains in `this.widgets` during this window.
   - On every subsequent loop iteration, `dockEntries[0]` continues to be the same first widget. Only the first widget is ever marked for dismissal; the remaining excess widgets are never evicted.
   - Verified via `adversarial_test.js`: All 8 widgets remained registered in `widgetManager.widgets` (`size = 8`), breaching `maxDockWidgets: 4`.

---

## 2. Logic Chain

1. **Safety and Soundness of Visual Layout & Three.js**:
   - From Observation 3, the layout places `#gen-ui-dock` and `.left-sidebar` at opposite edges (right: 34px and left: 34px), maintaining a clear 1244px central viewport.
   - Pointer events pass through `.ui-layer` because `pointer-events: none` is set on the container and only `.interactive` components capture events.
   - The absence of `backdrop-filter: blur(...)` prevents WebGL backbuffer blitting stalls in Chromium compositor.
   - Therefore, the Three.js 3D WebGL rendering canvas is not obstructed, covered by opaque backgrounds, or impaired by CSS repaint spikes.

2. **Safety and Soundness of Lifecycle & Memory Management**:
   - From Observation 4, click delegation on `document` avoids per-element event listeners.
   - `_teardownEntry` clears maps, removes DOM nodes, and nullifies references.
   - However, from Observation 6, rapid burst additions stall the FIFO eviction mechanism because `this.widgets` retains entries during their 380ms exit animation, causing `dockEntries[0]` to repeatedly point to the already-dismissing card while excess cards accumulate.

3. **Severity of DOM Injection Vulnerabilities**:
   - From Observation 5, while `WidgetTemplates` correctly uses `this._escape(...)` for titles and status labels, it omitted escaping on `data-metric-id` (lines 2553, 2569), `gVal` (line 2594), `variant` (line 2533), and `statusText` in the class attribute (line 2701).
   - In QtWebEngine Chromium, setting `cardEl.innerHTML` with broken-out attributes containing tags like `<img src=x onerror=...>` results in script execution in the desktop web view context.
   - This poses a critical security risk if telemetry, status, or metric data originates from external tools, plugins, or voice prompt parameters.

4. **Verdict Justification**:
   - The core functionality, UI layout, Three.js non-collision, and Pytest regression suites are excellent and fully passing.
   - However, the presence of verified DOM injection / attribute breakout vulnerabilities (Finding 1) is a Critical security flaw, and the burst eviction stall (Finding 2) is a Major functional flaw.
   - Under Quality & Adversarial Review principles, critical security vulnerabilities must be resolved before approval.
   - Therefore, the verdict is **`REQUEST_CHANGES`**.

---

## 3. Caveats

- **No Integrity Violations Detected**: The work was authored with genuine logic, clean CSS architecture, and passed all 140 project tests. The flaws found are subtle injection breakouts and race/burst boundary conditions discovered through white-box adversarial stress testing.
- **Backend Action Handlers**: Outbound action dispatching was verified on the frontend; inbound routing to Jarvis assistant methods in `web_bridge.py` is planned for Milestone 3 per `PROJECT.md`.

---

## 4. Conclusion & Required Changes

**Verdict**: **`REQUEST_CHANGES`**

### Findings Summary

#### [Critical] Finding 1: DOM Injection & Attribute Breakout in `WidgetTemplates`
- **Location**: `ui_improved.html` lines 2533, 2553, 2569, 2594, 2701
- **Vulnerability**:
  1. `data-metric-id="${m.id || m.label}"` (line 2553) and `data-metric-id="${k}"` (line 2569) lack escaping. Quotes break out of the attribute: `metric"><img src=x onerror=alert(1)>`.
  2. `<span class="gen-gauge-val">${gVal}</span>` (line 2594) interpolates raw string values.
  3. `<button class="gen-ui-btn ${variant}"` (line 2533) allows attribute injection via unescaped `act.variant`.
  4. `status-${statusText.toLowerCase()}` (line 2701) in class attribute allows attribute breakout.
- **Required Fix**:
  - Escape `m.id || m.label` and `k` with `this._escape(...)`.
  - Escape `gVal` with `this._escape(String(gVal))`.
  - Sanitize `variant` to alphanumeric/hyphen or escape it: `${this._escape(variant)}`.
  - Sanitize `statusText` class name using `.replace(/[^a-z0-9_-]/g, '')`.

#### [Major] Finding 2: FIFO Dock Capacity Eviction Stalls Under Burst Arrivals
- **Location**: `ui_improved.html` lines 2873-2879
- **Problem**: When widgets arrive rapidly, `dockEntries[0]` is repeatedly targeted while animating exit (`.dismissing`), leaving subsequent excess widgets on the dock and exceeding `maxDockWidgets`.
- **Required Fix**:
  - Filter for active non-dismissing entries:
    ```javascript
    const activeDockEntries = Array.from(this.widgets.values())
      .filter(e => e.target === 'dock' && (!e.containerEl || !e.containerEl.classList.contains('dismissing')));
    while (activeDockEntries.length >= this.maxDockWidgets) {
      const oldest = activeDockEntries.shift();
      this.dismissWidget(oldest.id, { immediate: false });
    }
    ```

#### [Minor] Finding 3: `querySelector` SyntaxError on Punctuation in Metric/Action Keys
- **Location**: `ui_improved.html` lines 2637, 2650, 2782
- **Problem**: Keys containing quotes or brackets (e.g. `metric "a"`) trigger DOMException `SyntaxError` when passed directly into query selector strings.
- **Suggested Fix**: Use `CSS.escape(...)` if available, or compare `dataset.metricId === key` / `dataset.actionId === key`.

---

## 5. Verification Method

To independently verify these findings and confirm resolution:

1. **Execute Node.js Adversarial Verification Script**:
   ```powershell
   Set-Location C:\jarvis\Mark-LV-main\Mark-LV-main
   node .\.agents\teamwork\teamwork_reviewer_m2_2\adversarial_test.js
   ```
   *Current output*: Confirms DOM injection PoC exploits and burst capacity breach.
   *Resolution condition*: Must output `SAFE` across all injection checks and `Burst capacity limit breached: NO`.

2. **Execute Full Pytest Suite**:
   ```powershell
   Set-Location C:\jarvis\Mark-LV-main\Mark-LV-main
   .\.venv\Scripts\python.exe -m pytest tests/test_ui_standardization.py tests/test_web_bridge_e2e.py -v
   .\.venv\Scripts\python.exe -m pytest -v
   ```
   *Expected outcome*: 139 passed, 1 skipped, 0 failures.
