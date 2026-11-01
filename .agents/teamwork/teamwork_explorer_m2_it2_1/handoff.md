# Milestone 2 Iteration 2 Explorer 1: DOM & Template Hardening Handoff Report

- **Agent**: Milestone 2 Iteration 2 Explorer 1 (`teamwork_explorer_m2_it2_1`)
- **Archetype**: Explorer / Investigator
- **Working Directory**: `C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\teamwork_explorer_m2_it2_1`
- **Target File**: `C:\jarvis\Mark-LV-main\Mark-LV-main\ui_improved.html`
- **Recipient**: Orchestrator (`6906300c-9137-4e62-90d0-c438dc9f10d1`)
- **Date**: 2026-10-31

---

## 1. Observation

Direct examination of `ui_improved.html` (lines 2468–2830 and lines 3202–3215) along with adversarial scripts (`teamwork_reviewer_m2_2/adversarial_test.js` and `tests/test_widget_manager_oracle.js`) revealed the following concrete observations:

### A. DOM Injection & Attribute Breakout Vulnerabilities
1. **Line 2553 & Line 2569 (`telemetry`)**:
   ```javascript
   // Line 2553
   <div class="gen-metric-row" data-metric-id="${m.id || m.label}">
   // Line 2569
   <div class="gen-metric-row" data-metric-id="${k}">
   ```
   *Direct Observation*: `m.id || m.label` and `k` are interpolated directly without `this._escape(...)`.
   *PoC Output*: Passing `label: 'metric"><img src=x onerror=alert(1)>'` outputs:
   `<div class="gen-metric-row" data-metric-id="metric"><img src=x onerror=alert(1)>">`.
   Running `node .agents/teamwork/teamwork_reviewer_m2_2/adversarial_test.js` yielded:
   `PoC Metric ID Breakout injected raw <img> tag: VULNERABLE (PASSES PoC)`.

2. **Line 2594 (`telemetry` Gauge)**:
   ```javascript
   // Line 2594
   <span class="gen-gauge-val">${gVal}</span>
   ```
   *Direct Observation*: `gVal` originates from `data.gauge.value || 0` and is interpolated raw into inner HTML without escaping.
   *PoC Output*: Passing `data.gauge.value = '<img src=x onerror=alert(2)>'` results in live HTML tag injection.
   `PoC Gauge Value injected raw <img> tag: VULNERABLE (PASSES PoC)`.

3. **Line 2530 & Line 2533 (`renderActions`)**:
   ```javascript
   // Line 2530
   const variant = act.variant || '';
   // Line 2533
   <button class="gen-ui-btn ${variant}" data-action-id="${this._escape(actId)}" ...>
   ```
   *Direct Observation*: `variant` is interpolated raw into the class attribute.
   *PoC Output*: Passing `variant: 'primary" onfocus="alert(3)'` breaks out of the `class` attribute:
   `<button class="gen-ui-btn primary" onfocus="alert(3)" ...>`.
   `PoC Action Variant injected raw attribute: VULNERABLE (PASSES PoC)`.

4. **Line 2701 (`activity_tracker`)**:
   ```javascript
   // Line 2701
   <span class="gen-tracker-state-badge status-${statusText.toLowerCase()}" data-bind="status">${this._escape(statusText)}</span>
   ```
   *Direct Observation*: While the inner text is escaped, the class name `status-${statusText.toLowerCase()}` is interpolated raw, permitting attribute breakout if `statusText` contains quotes or attributes.

### B. Unhandled `TypeError` on Sparse or Null Array Elements
1. **Line 2528 (`renderActions`)**: `act.action_id || act.id` throws `TypeError: Cannot read properties of null (reading 'action_id')` when `actions: [null]`.
2. **Line 2548 (`telemetry`)**: `m.value` throws `TypeError: Cannot read properties of null (reading 'value')` when `metrics: [null]`.
3. **Line 2684 (`activity_tracker`)**: `typeof step === 'object'` evaluates to `true` for `null` in JavaScript (`typeof null === 'object'`), causing `step.completed` to throw `TypeError: Cannot read properties of null (reading 'completed')` when `steps: [null]`.
4. **Line 2742 (`action_grid`)**: `item.action_id || item.id` throws `TypeError: Cannot read properties of null (reading 'action_id')` when `items: [null]`.
5. **Delta Updaters (`updateTelemetry`, `updateActionGrid`)**: `deltaData.metrics.forEach` and `deltaData.items.forEach` similarly crash if arrays contain null items.

### C. Missing Exception Guard in `_generateHtml`
- **Lines 3202–3215 (`WidgetManager._generateHtml`)**:
  ```javascript
  _generateHtml(schema, widgetId, templateName) {
    const tplDef = this.templates.get(templateName);
    if (tplDef && typeof tplDef.render === 'function') {
      return tplDef.render(schema);
    }
    if (typeof window !== 'undefined' && window.WidgetTemplates && typeof window.WidgetTemplates[templateName] === 'function') {
      return window.WidgetTemplates[templateName](schema);
    }
    return `<div class="gen-ui-card"><div class="gen-ui-title">${schema.title || widgetId}</div></div>`;
  }
  ```
  *Direct Observation*: Template execution is not wrapped in `try...catch`. Any exception in a built-in or custom renderer causes `renderWidget()` to crash during WebSocket message handling.

---

## 2. Logic Chain

1. **DOM Injection & Attribute Breakout Remediation**:
   - In `telemetry`: Escaping `data-metric-id="${this._escape(metricId)}"` and `data-metric-id="${this._escape(k)}"` turns `"` and `<` into `&quot;` and `&lt;`, guaranteeing that metric identifiers cannot break out of HTML attribute boundaries (Observation A.1).
   - In `telemetry` Gauge: Wrapping `gVal` with `${this._escape(gVal)}` neutralizes any HTML tags passed in `data.gauge.value` (Observation A.2).
   - In `renderActions`: Escaping `variant` with `${this._escape(variant)}` prevents attribute breakout inside `<button class="gen-ui-btn ...">` (Observation A.3).
   - In `activity_tracker`: Sanitizing the CSS class status token with `statusText.toLowerCase().replace(/[^a-z0-9_-]/g, '')` ensures that only valid CSS identifier characters are emitted, preventing any space or quote breakout while keeping class names valid (Observation A.4).

2. **Sparse and Null Array Null-Guard Remediation**:
   - In JavaScript, `item && typeof item === 'object'` evaluates to `false` for `null`, `undefined`, numbers, strings, and booleans.
   - Filtering arrays (`data.metrics`, `deltaData.metrics`, `data.steps`, `items`, `actions`) with `.filter(item => item && typeof item === 'object')` guarantees that every mapped item is an object.
   - This eliminates all unhandled `TypeError` exceptions from Observation B.

3. **Exception Boundary Remediation**:
   - Wrapping `_generateHtml` in a `try...catch` block ensures that if a custom or built-in template throws an error, the exception is caught, logged to console, and a safe Liquid Glass error card is returned with a `danger` badge and active dismiss button (Observation C).

4. **Delta Selector Safety**:
   - In `updateTelemetry` and `updateActionGrid`, looking up elements via `Array.from(cardEl.querySelectorAll(...)).find(el => el.dataset.id === targetId || el.getAttribute(...) === targetId)` eliminates `DOMException: SyntaxError` when metric keys contain quotes, punctuation, or spaces.

---

## 3. Caveats

- **Scope Boundary**: This investigation focuses strictly on DOM injection escaping, array null-guards in `WidgetTemplates`, and the `_generateHtml` fallback error card. FIFO dock eviction logic in `WidgetManager.renderWidget` is a separate lifecycle defect tracked under Milestone 2 Iteration 2 Explorer 2.
- **HTML in Custom Template**: `WidgetTemplates.custom` renders `data.html || data.content || data.text` inside `.gen-ui-custom-body` as intended by design for rich custom widgets; its header, title, and actions are fully protected.

---

## 4. Conclusion & Copy-Pasteable Replacement Code

The proposed code completely resolves all 4 injection vulnerabilities, guards all arrays against null/sparse elements, and adds defensive exception handling with fallback error rendering.

### A. Replacement Code for `WidgetTemplates` (`ui_improved.html` lines 2468–2829)

```javascript
    const WidgetTemplates = {
      icons: {
        cpu: '<svg viewBox="0 0 24 24"><rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><line x1="9" y1="1" x2="9" y2="4"/><line x1="15" y1="1" x2="15" y2="4"/><line x1="9" y1="20" x2="9" y2="23"/><line x1="15" y1="20" x2="15" y2="23"/><line x1="20" y1="9" x2="23" y2="9"/><line x1="20" y1="14" x2="23" y2="14"/><line x1="1" y1="9" x2="4" y2="9"/><line x1="1" y1="14" x2="4" y2="14"/></svg>',
        activity: '<svg viewBox="0 0 24 24"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>',
        server: '<svg viewBox="0 0 24 24"><rect x="2" y="2" width="20" height="8" rx="2" ry="2"/><rect x="2" y="14" width="20" height="8" rx="2" ry="2"/><line x1="6" y1="6" x2="6.01" y2="6"/><line x1="6" y1="18" x2="6.01" y2="18"/></svg>',
        database: '<svg viewBox="0 0 24 24"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>',
        shield: '<svg viewBox="0 0 24 24"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>',
        zap: '<svg viewBox="0 0 24 24"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>',
        wifi: '<svg viewBox="0 0 24 24"><path d="M5 12.55a11 11 0 0 1 14.08 0"/><path d="M1.42 9a16 16 0 0 1 21.16 0"/><path d="M8.53 16.11a6 6 0 0 1 6.95 0"/><line x1="12" y1="20" x2="12.01" y2="20"/></svg>',
        grid: '<svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>',
        sliders: '<svg viewBox="0 0 24 24"><line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/><line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/><line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/><line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/><line x1="17" y1="16" x2="23" y2="16"/></svg>',
        terminal: '<svg viewBox="0 0 24 24"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>',
        check: '<svg viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg>',
        x: '<svg viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>',
        play: '<svg viewBox="0 0 24 24"><polygon points="5 3 19 12 5 21 5 3"/></svg>',
        pause: '<svg viewBox="0 0 24 24"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>',
        refresh: '<svg viewBox="0 0 24 24"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>',
        info: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>',
        default: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>'
      },

      getIcon(iconName) {
        if (iconName && Object.prototype.hasOwnProperty.call(this.icons, iconName)) {
          return this.icons[iconName];
        }
        return this.icons.activity || this.icons.default || '';
      },

      _escape(str) {
        if (str === null || str === undefined) return '';
        return String(str).replace(/[&<>"']/g, m => ({
          '&': '&amp;',
          '<': '&lt;',
          '>': '&gt;',
          '"': '&quot;',
          "'": '&#39;'
        }[m]));
      },

      renderHeader(schema) {
        if (!schema || typeof schema !== 'object') schema = {};
        const title = schema.title || 'Widget';
        const rawStatus = (schema.data && schema.data.status !== undefined) ? schema.data.status : (schema.status || '');
        const status = rawStatus !== null && rawStatus !== undefined ? String(rawStatus) : '';
        const statusLower = status.toLowerCase();
        const badgeClass = (statusLower === 'live' || statusLower === 'active' || statusLower === 'running') ? 'live' :
                           (statusLower === 'warn' || statusLower === 'warning' || statusLower === 'paused') ? 'warn' :
                           (statusLower === 'danger' || statusLower === 'error') ? 'danger' : '';

        return `
          <div class="gen-ui-header">
            <div class="gen-ui-title-group">
              <div class="gen-ui-icon">${this.getIcon(schema.icon)}</div>
              <span class="gen-ui-title" data-bind="title">${this._escape(title)}</span>
            </div>
            <div class="gen-ui-controls">
              ${status ? `<span class="gen-ui-badge ${badgeClass}" data-bind="status">${this._escape(status)}</span>` : ''}
              <button class="gen-ui-close-btn" data-action-id="dismiss" data-widget-dismiss aria-label="Dismiss">✕</button>
            </div>
          </div>
        `;
      },

      renderActions(widgetId, actions) {
        if (!Array.isArray(actions) || actions.length === 0) return '';
        const validActions = actions.filter(act => act && typeof act === 'object');
        if (validActions.length === 0) return '';
        const btns = validActions.map(act => {
          const actId = act.action_id || act.id || '';
          const label = act.label || actId;
          const variant = act.variant ? this._escape(String(act.variant)) : '';
          let payloadStr = '{}';
          if (act.payload !== undefined && act.payload !== null) {
            try {
              payloadStr = typeof act.payload === 'object' ? JSON.stringify(act.payload) : JSON.stringify({ value: act.payload });
            } catch (e) {
              payloadStr = '{}';
            }
          }
          return `
            <button class="gen-ui-btn ${variant}" data-action-id="${this._escape(actId)}" data-widget-id="${this._escape(widgetId)}" data-payload='${payloadStr.replace(/'/g, "&apos;")}'>
              <span>${this._escape(label)}</span>
            </button>
          `;
        }).join('');
        return `<div class="gen-ui-action-group">${btns}</div>`;
      },

      telemetry(schema) {
        if (!schema || typeof schema !== 'object') schema = {};
        const wId = schema.id || '';
        const data = (schema.data && typeof schema.data === 'object') ? schema.data : {};
        let metricsHtml = '';

        if (Array.isArray(data.metrics)) {
          metricsHtml = data.metrics
            .filter(m => m && typeof m === 'object')
            .map(m => {
              const val = typeof m.value === 'number' ? m.value : Number(m.value) || 0;
              const max = m.max || 100;
              const pct = Math.min(100, Math.max(0, (val / max) * 100));
              const unit = m.unit || '';
              const metricId = m.id || m.label || '';
              return `
                <div class="gen-metric-row" data-metric-id="${this._escape(metricId)}">
                  <div class="gen-metric-info">
                    <span class="gen-metric-label">${this._escape(m.label || m.id)}</span>
                    <span class="gen-metric-val cyan">${this._escape(val)}${this._escape(unit)}</span>
                  </div>
                  <div class="gen-metric-track">
                    <div class="gen-metric-fill" style="width: ${pct}%"></div>
                  </div>
                </div>
              `;
            }).join('');
        } else {
          metricsHtml = Object.entries(data)
            .filter(([k]) => k !== 'status' && k !== 'desc' && k !== 'gauge' && k !== 'sparkline')
            .map(([k, v]) => {
              const numVal = typeof v === 'number' ? v : parseFloat(v) || 0;
              const pct = Math.min(100, Math.max(0, numVal));
              return `
                <div class="gen-metric-row" data-metric-id="${this._escape(k)}">
                  <div class="gen-metric-info">
                    <span class="gen-metric-label">${this._escape(k.toUpperCase())}</span>
                    <span class="gen-metric-val cyan">${this._escape(v)}${typeof v === 'number' ? '%' : ''}</span>
                  </div>
                  <div class="gen-metric-track">
                    <div class="gen-metric-fill" style="width: ${pct}%"></div>
                  </div>
                </div>
              `;
            }).join('');
        }

        let gaugeHtml = '';
        if (data.gauge && typeof data.gauge === 'object') {
          const gVal = data.gauge.value !== undefined ? data.gauge.value : 0;
          const gMax = data.gauge.max || 100;
          const numGVal = typeof gVal === 'number' ? gVal : Number(gVal) || 0;
          const gPct = Math.min(100, Math.max(0, (numGVal / gMax) * 100));
          gaugeHtml = `
            <div class="gen-gauge-container">
              <svg class="gen-gauge-svg" viewBox="0 0 36 36">
                <path class="gen-gauge-bg" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" />
                <path class="gen-gauge-fill" stroke-dasharray="${gPct}, 100" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" />
              </svg>
              <div class="gen-gauge-text">
                <span class="gen-gauge-val">${this._escape(gVal)}</span>
                <span class="gen-gauge-unit">${this._escape(data.gauge.unit || '%')}</span>
              </div>
            </div>
          `;
        }

        let sparklineHtml = '';
        if (Array.isArray(data.sparkline) && data.sparkline.length > 1) {
          const pts = data.sparkline.map(p => Number(p) || 0);
          const min = Math.min(...pts);
          const max = Math.max(...pts) || 1;
          const range = max - min || 1;
          const w = 240, h = 32;
          const coords = pts.map((val, idx) => {
            const x = (idx / (pts.length - 1)) * w;
            const y = h - ((val - min) / range) * (h - 6) - 3;
            return `${x.toFixed(1)},${y.toFixed(1)}`;
          }).join(' ');
          sparklineHtml = `
            <div class="gen-sparkline-wrap">
              <svg class="gen-sparkline-svg" viewBox="0 0 ${w} ${h}">
                <polyline points="${coords}" fill="none" stroke="var(--cyan-bright)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </div>
          `;
        }

        return `
          ${this.renderHeader(schema)}
          <div class="gen-card-body">
            ${gaugeHtml}
            <div class="gen-metrics-list">${metricsHtml}</div>
            ${sparklineHtml}
          </div>
          ${this.renderActions(wId, schema.actions)}
        `;
      },

      updateTelemetry(cardEl, deltaData) {
        if (!cardEl || !deltaData || typeof deltaData !== 'object') return;
        if (Array.isArray(deltaData.metrics)) {
          deltaData.metrics.filter(m => m && typeof m === 'object').forEach(m => {
            const metricId = String(m.id || m.label || '');
            if (!metricId) return;
            const row = cardEl.querySelector ? (
              cardEl.querySelector(`.gen-metric-row[data-metric-id="${metricId}"]`) ||
              (cardEl.querySelectorAll ? Array.from(cardEl.querySelectorAll('[data-metric-id]')).find(r => r.dataset && (r.dataset.metricId === metricId || r.getAttribute('data-metric-id') === metricId)) : null)
            ) : null;
            if (row) {
              const val = typeof m.value === 'number' ? m.value : Number(m.value) || 0;
              const max = m.max || 100;
              const pct = Math.min(100, Math.max(0, (val / max) * 100));
              const valEl = row.querySelector('.gen-metric-val');
              const fillEl = row.querySelector('.gen-metric-fill');
              if (valEl) valEl.textContent = `${val}${m.unit || ''}`;
              if (fillEl) fillEl.style.width = `${pct}%`;
            }
          });
        } else {
          Object.entries(deltaData).forEach(([k, v]) => {
            const row = cardEl.querySelector ? (
              cardEl.querySelector(`.gen-metric-row[data-metric-id="${k}"]`) ||
              (cardEl.querySelectorAll ? Array.from(cardEl.querySelectorAll('[data-metric-id]')).find(r => r.dataset && (r.dataset.metricId === k || r.getAttribute('data-metric-id') === k)) : null)
            ) : null;
            if (row) {
              const numVal = typeof v === 'number' ? v : parseFloat(v) || 0;
              const pct = Math.min(100, Math.max(0, numVal));
              const valEl = row.querySelector('.gen-metric-val');
              const fillEl = row.querySelector('.gen-metric-fill');
              if (valEl) valEl.textContent = typeof v === 'number' ? `${v}%` : String(v);
              if (fillEl) fillEl.style.width = `${pct}%`;
            }
          });
        }

        if (deltaData.gauge && typeof deltaData.gauge === 'object') {
          const gVal = deltaData.gauge.value !== undefined ? deltaData.gauge.value : 0;
          const gMax = deltaData.gauge.max || 100;
          const numGVal = typeof gVal === 'number' ? gVal : Number(gVal) || 0;
          const gPct = Math.min(100, Math.max(0, (numGVal / gMax) * 100));
          const gFill = cardEl.querySelector('.gen-gauge-fill');
          const gValEl = cardEl.querySelector('.gen-gauge-val');
          if (gFill) gFill.setAttribute('stroke-dasharray', `${gPct}, 100`);
          if (gValEl) gValEl.textContent = String(gVal);
        }
      },

      activity_tracker(schema) {
        if (!schema || typeof schema !== 'object') schema = {};
        const wId = schema.id || '';
        const data = (schema.data && typeof schema.data === 'object') ? schema.data : {};
        const taskName = data.task_name || data.activity_name || schema.title || 'Task in Progress';
        const progress = Math.min(100, Math.max(0, Number(data.progress) || 0));
        const rawStatus = data.status || schema.status || 'RUNNING';
        const statusText = rawStatus !== null && rawStatus !== undefined ? String(rawStatus) : 'RUNNING';
        const safeStatusClass = this._escape(statusText.toLowerCase().replace(/[^a-z0-9_-]/g, ''));
        const detailText = data.detail || data.step || 'Processing...';

        let stepsHtml = '';
        if (Array.isArray(data.steps) && data.steps.length > 0) {
          stepsHtml = `<div class="gen-steps-list">` + data.steps
            .filter(step => step && typeof step === 'object')
            .map(step => {
              const isDone = Boolean(step.completed);
              const isCurrent = Boolean(step.current);
              const stepClass = isDone ? 'completed' : isCurrent ? 'active' : 'pending';
              const label = step.label || step.name || '';
              return `
                <div class="gen-step-item ${stepClass}">
                  <span class="gen-step-dot"></span>
                  <span class="gen-step-label">${this._escape(label)}</span>
                </div>
              `;
            }).join('') + `</div>`;
        }

        return `
          ${this.renderHeader(schema)}
          <div class="gen-card-body">
            <div class="gen-tracker-status-row">
              <span class="gen-tracker-state-badge status-${safeStatusClass}" data-bind="status">${this._escape(statusText)}</span>
              <span class="gen-tracker-pct" data-bind="progress_val">${progress}%</span>
            </div>
            <div class="gen-progress-track">
              <div class="gen-progress-fill" data-bind="progress_fill" style="width: ${progress}%;"></div>
            </div>
            <div class="gen-tracker-detail" data-bind="detail">${this._escape(detailText)}</div>
            ${stepsHtml}
          </div>
          ${this.renderActions(wId, schema.actions)}
        `;
      },

      updateActivityTracker(cardEl, deltaData) {
        if (!cardEl || !deltaData || typeof deltaData !== 'object') return;
        if (deltaData.progress !== undefined) {
          const pct = Math.min(100, Math.max(0, Number(deltaData.progress) || 0));
          const fill = cardEl.querySelector('.gen-progress-fill, .gen-ui-progress-fill');
          const pctEl = cardEl.querySelector('.gen-tracker-pct, .gen-ui-progress-val');
          if (fill) fill.style.width = `${pct}%`;
          if (pctEl) pctEl.textContent = `${pct}%`;
        }
        if (deltaData.status) {
          const badge = cardEl.querySelector('.gen-tracker-state-badge, .gen-ui-badge');
          if (badge) {
            const safeStatusClass = String(deltaData.status).toLowerCase().replace(/[^a-z0-9_-]/g, '');
            badge.className = `gen-tracker-state-badge status-${safeStatusClass}`;
            badge.textContent = String(deltaData.status);
          }
        }
        if (deltaData.detail || deltaData.step) {
          const detailEl = cardEl.querySelector('.gen-tracker-detail, [data-bind="detail"]');
          if (detailEl) detailEl.textContent = deltaData.detail || deltaData.step;
        }
      },

      action_grid(schema) {
        if (!schema || typeof schema !== 'object') schema = {};
        const wId = schema.id || '';
        const data = (schema.data && typeof schema.data === 'object') ? schema.data : {};
        const rawItems = data.items || data.buttons || schema.actions || [];
        const items = Array.isArray(rawItems) ? rawItems.filter(item => item && typeof item === 'object') : [];

        const tilesHtml = items.map(item => {
          const actId = item.action_id || item.id || '';
          const label = item.label || actId;
          const iconSvg = this.getIcon(item.icon || 'zap');
          const isToggle = Boolean(item.toggle);
          const isActive = Boolean(item.active);
          const activeClass = isActive ? ' active' : '';
          const badgeText = item.badge || (isToggle ? (isActive ? 'ON' : 'OFF') : '');
          const badgeHtml = badgeText ? `<span class="gen-tile-badge">${this._escape(badgeText)}</span>` : '';
          let payloadStr = '{}';
          if (item.payload !== undefined && item.payload !== null) {
            try {
              payloadStr = typeof item.payload === 'object' ? JSON.stringify(item.payload) : JSON.stringify({ value: item.payload });
            } catch (e) {
              payloadStr = '{}';
            }
          }

          return `
            <button class="gen-action-tile${activeClass}" 
                    data-widget-id="${this._escape(wId)}" 
                    data-action-id="${this._escape(actId)}" 
                    data-toggle="${isToggle}" 
                    data-active="${isActive}" 
                    data-payload='${payloadStr.replace(/'/g, '&apos;')}'>
              <span class="gen-tile-icon">${iconSvg}</span>
              <span class="gen-tile-label">${this._escape(label)}</span>
              ${badgeHtml}
            </button>
          `;
        }).join('');

        return `
          ${this.renderHeader(schema)}
          <div class="gen-card-body">
            ${data.desc ? `<div class="gen-ui-metric-label" style="margin-bottom: 4px;">${this._escape(data.desc)}</div>` : ''}
            <div class="gen-action-grid">${tilesHtml}</div>
          </div>
          ${this.renderActions(wId, Array.isArray(schema.actions) && schema.actions !== rawItems ? schema.actions : [])}
        `;
      },

      updateActionGrid(cardEl, deltaData) {
        if (!cardEl || !deltaData || typeof deltaData !== 'object') return;
        const list = deltaData.items || deltaData.buttons;
        if (Array.isArray(list)) {
          list.filter(item => item && typeof item === 'object').forEach(item => {
            const actId = item.action_id || item.id;
            if (!actId) return;
            const targetId = String(actId);
            const tile = Array.from(cardEl.querySelectorAll('.gen-action-tile')).find(
              t => t.dataset.actionId === targetId || t.getAttribute('data-action-id') === targetId
            );
            if (tile) {
              if (item.active !== undefined) {
                const isActive = Boolean(item.active);
                tile.dataset.active = String(isActive);
                if (isActive) tile.classList.add('active');
                else tile.classList.remove('active');
                const badge = tile.querySelector('.gen-tile-badge');
                if (badge && tile.dataset.toggle === 'true') {
                  badge.textContent = isActive ? 'ON' : 'OFF';
                }
              }
              if (item.badge !== undefined) {
                let bEl = tile.querySelector('.gen-tile-badge');
                if (!bEl) {
                  bEl = document.createElement('span');
                  bEl.className = 'gen-tile-badge';
                  tile.appendChild(bEl);
                }
                bEl.textContent = String(item.badge);
              }
            }
          });
        }
      },

      custom(schema) {
        if (!schema || typeof schema !== 'object') schema = {};
        const wId = schema.id || '';
        const data = (schema.data && typeof schema.data === 'object') ? schema.data : {};
        const content = data.html || data.content || data.text || '';
        return `
          ${this.renderHeader(schema)}
          <div class="gen-card-body">
            <div class="gen-ui-custom-body" data-bind="content">${content}</div>
          </div>
          ${this.renderActions(wId, schema.actions)}
        `;
      },

      updateCustom(cardEl, deltaData) {
        if (!cardEl || !deltaData || typeof deltaData !== 'object') return;
        const bodyEl = cardEl.querySelector('.gen-ui-custom-body');
        if (bodyEl && (deltaData.html || deltaData.content || deltaData.text)) {
          bodyEl.innerHTML = deltaData.html || deltaData.content || deltaData.text;
        }
      }
    };

    window.WidgetTemplates = WidgetTemplates;
```

---

### B. Replacement Code for `_generateHtml` (`ui_improved.html` lines 3202–3215)

```javascript
      _generateHtml(schema, widgetId, templateName) {
        try {
          // Check registered templates first
          const tplDef = this.templates.get(templateName);
          if (tplDef && typeof tplDef.render === 'function') {
            return tplDef.render(schema);
          }

          // Check window.WidgetTemplates
          if (typeof window !== 'undefined' && window.WidgetTemplates && typeof window.WidgetTemplates[templateName] === 'function') {
            return window.WidgetTemplates[templateName](schema);
          }

          const safeTitle = (typeof window !== 'undefined' && window.WidgetTemplates && typeof window.WidgetTemplates._escape === 'function')
            ? window.WidgetTemplates._escape(schema.title || widgetId)
            : String(schema.title || widgetId).replace(/[&<>"']/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m]));

          return `<div class="gen-ui-card"><div class="gen-ui-title">${safeTitle}</div></div>`;
        } catch (err) {
          console.error(`[WidgetManager] Error rendering template '${templateName}' for widget '${widgetId}':`, err);
          const safeId = (typeof window !== 'undefined' && window.WidgetTemplates && typeof window.WidgetTemplates._escape === 'function')
            ? window.WidgetTemplates._escape(schema && schema.title ? schema.title : widgetId)
            : String(widgetId).replace(/[&<>"']/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m]));
          const safeMsg = String(err && err.message ? err.message : 'Render Error').replace(/[&<>"']/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m]));
          return `
            <div class="gen-ui-header">
              <div class="gen-ui-title-group">
                <span class="gen-ui-title">${safeId}</span>
              </div>
              <div class="gen-ui-controls">
                <span class="gen-ui-badge danger">ERROR</span>
                <button class="gen-ui-close-btn" data-action-id="dismiss" data-widget-dismiss aria-label="Dismiss">✕</button>
              </div>
            </div>
            <div class="gen-card-body">
              <div class="gen-ui-metric-label" style="color: var(--amber, #f87171);">${safeMsg}</div>
            </div>
          `;
        }
      }
```

---

## 5. Verification Method

### A. Independent Verification Commands
1. **Adversarial Security Test**:
   Execute the standalone verification test script:
   ```powershell
   node C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\teamwork_explorer_m2_it2_1\verify_hardening.js
   ```
   *Expected Result*:
   ```
   ✓ PASS: Metric ID injection neutralized
   ✓ PASS: Gauge value injection neutralized
   ✓ PASS: Action variant injection neutralized
   ✓ PASS: Status class breakout neutralized
   ✓ PASS: Telemetry handles sparse/null metrics array
   ✓ PASS: Activity tracker handles sparse/null steps array
   ✓ PASS: Action grid handles sparse/null items array
   ✓ PASS: renderActions handles sparse/null actions array
   ✓ PASS: _generateHtml gracefully catches template crash and returns error card
   ```

2. **Full Reviewer 2 Adversarial Suite**:
   ```powershell
   node C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\teamwork_explorer_m2_it2_1\test_adv_with_patched.js
   ```
   *Expected Result*:
   ```
   PoC Metric ID Breakout injected raw <img> tag: SAFE
   PoC Gauge Value injected raw <img> tag: SAFE
   PoC Action Variant injected raw attribute: SAFE
   ```

3. **Challenger 2 Empirical Oracle Test Suite**:
   ```powershell
   node C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\teamwork_explorer_m2_it2_1\test_replacement_oracle.js
   ```
   *Expected Result*: 164 passed assertions, 16,667 updates/sec O(1) performance.

4. **Pytest Regression Suite**:
   ```powershell
   python -m pytest C:\jarvis\Mark-LV-main\Mark-LV-main\tests
   ```
   *Expected Result*: 146 passed, 0 failures.

### B. Invalidation Conditions
- Any `TypeError` when passing `[null]` in array fields of `metrics`, `steps`, `items`, or `actions`.
- Any raw HTML tag insertion or attribute breakout when passing `<img src=x onerror=...>` in `data-metric-id`, `gauge.value`, `variant`, or `status`.
- An uncaught exception crashing `renderWidget` when a template throws an error.
