# Survey Report: Generative UI Widget Templates, Interaction & WebSocket Integration

**Agent**: Milestone 2 Explorer 3 (`teamwork_explorer_m2_3`)  
**Working Directory**: `C:\jarvis\Mark-LV-main\Mark-LV-main\.agents\teamwork\teamwork_explorer_m2_3`  
**Target Codebase**: `C:\jarvis\Mark-LV-main\Mark-LV-main`  
**Scope**: Widget Templates (`telemetry`, `activity_tracker`, `action_grid`), Inbound WebSocket Handlers (`widget_render`, `widget_update`, `widget_dismiss`), and Outbound Action Dispatching (`widget_action`) in `ui_improved.html`  
**Date**: 2026-10-31  

---

## 1. Executive Summary

This investigation designs and specifies the complete template generation, event interaction, and WebSocket communication layer for Milestone 2 Generative UI in `ui_improved.html`.

### Key Outcomes:
1. **Three Core Interactive Templates**:
   - `telemetry`: Circular SVG gauges, live metric progress bars, historical sparklines, and status badges, supporting both structured metric collections and flat metric key-value dictionaries.
   - `activity_tracker`: Real-time workflow & job progress bars, state indicators (`RUNNING`, `QUEUED`, `COMPLETED`, `PAUSED`, `ERROR`), detail steps, and pause/cancel/retry action controls.
   - `action_grid`: Responsive Control Center tile grid with momentary action buttons, stateful toggle switches (with instant UI feedback), and parameterized command dispatchers.
   - `custom` fallback template for arbitrary HTML or structured JSON diagnostics.
2. **Built-in Standalone SVG Icon Registry**:
   - 16+ inline vector SVGs matching the Apple visionOS Liquid Glass aesthetic of `ui_improved.html` with zero external web font or CDN dependencies.
3. **Inbound WebSocket Protocol Handlers**:
   - Exact insertion point in `ui_improved.html` (`ws.onmessage`, lines 1881–1883) for `widget_render`, `widget_update`, and `widget_dismiss`.
4. **Outbound User Action Dispatch Pipeline**:
   - Centralized `sendWidgetAction(widgetId, actionId, payload)` helper communicating via WebSocket `/ws`.
   - Procedural Web Audio API sound feedback via `sfx.click()`.
   - Document-level event delegation on `[data-action-id]` ensuring memory safety and dynamic element handling without manual event binding.
5. **Compositor Safety & Non-Interference**:
   - Strict avoidance of `backdrop-filter: blur(...)` to prevent Qt WebEngine GPU stutter over the Three.js WebGL canvas, leveraging `--glass-surface`, `--glass-specular`, and hardware-accelerated CSS transitions.

---

## 2. Interface Contract Alignment

All designs strictly conform to the contracts defined in `PROJECT.md` and verified in `tests/test_web_bridge_e2e.py:test_generative_ui_interface_contracts_validity`:

### 2.1 Inbound Messages (Server -> Frontend)

```json
// 1. widget_render
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

// 2. widget_update
{
  "type": "widget_update",
  "widget_id": "diag_sys_status",
  "data": { ... }
}

// 3. widget_dismiss
{
  "type": "widget_dismiss",
  "widget_id": "diag_sys_status"
}
```

### 2.2 Outbound Messages (Frontend -> Server)

```json
// widget_action
{
  "type": "widget_action",
  "widget_id": "diag_sys_status",
  "action_id": "refresh",
  "payload": { ... }
}
```

---

## 3. Template Architecture Specifications

### 3.1 Icon Registry
All templates resolve icons through `WidgetTemplates.getIcon(name)`. Vector paths use `viewBox="0 0 24 24"`, `stroke="currentColor"`, `stroke-width="2"`, `fill="none"`:

```javascript
const WidgetIcons = {
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
};
```

---

### 3.2 Template 1: `telemetry`

#### Structure:
- **Header**: Icon, Title, optional Status pill, Dismiss button.
- **Circular Gauge (Optional)**: If `data.gauge` is present, renders a circular SVG ring with `stroke-dasharray` and tabular percentage.
- **Metrics List**: Supports both:
  1. Structured array: `data.metrics: [{ id: "cpu", label: "CPU", value: 45, unit: "%", max: 100 }]`
  2. Flat key-value dict: `data: { "cpu": 15.2, "ram": 42.1 }`
- **Sparkline (Optional)**: If `data.sparkline` is present (array of numbers), renders an SVG polyline trend curve.
- **Actions Footer**: Buttons (`primary`, `secondary`, `danger`, `outline`).

#### DOM Generator Code:
```javascript
telemetry(schema) {
  const wId = schema.id;
  const data = schema.data || {};
  let metricsHtml = '';

  if (Array.isArray(data.metrics)) {
    metricsHtml = data.metrics.map(m => {
      const val = typeof m.value === 'number' ? m.value : Number(m.value) || 0;
      const max = m.max || 100;
      const pct = Math.min(100, Math.max(0, (val / max) * 100));
      const unit = m.unit || '';
      return `
        <div class="gen-metric-row" data-metric-id="${m.id || m.label}">
          <div class="gen-metric-info">
            <span class="gen-metric-label">${m.label || m.id}</span>
            <span class="gen-metric-val">${val}${unit}</span>
          </div>
          <div class="gen-metric-track">
            <div class="gen-metric-fill" style="width: ${pct}%"></div>
          </div>
        </div>
      `;
    }).join('');
  } else {
    metricsHtml = Object.entries(data).filter(([k]) => k !== 'gauge' && k !== 'sparkline').map(([k, v]) => {
      const numVal = typeof v === 'number' ? v : parseFloat(v) || 0;
      const pct = Math.min(100, Math.max(0, numVal));
      return `
        <div class="gen-metric-row" data-metric-id="${k}">
          <div class="gen-metric-info">
            <span class="gen-metric-label">${k.toUpperCase()}</span>
            <span class="gen-metric-val">${numVal}%</span>
          </div>
          <div class="gen-metric-track">
            <div class="gen-metric-fill" style="width: ${pct}%"></div>
          </div>
        </div>
      `;
    }).join('');
  }

  let gaugeHtml = '';
  if (data.gauge) {
    const gVal = data.gauge.value || 0;
    const gMax = data.gauge.max || 100;
    const gPct = Math.min(100, Math.max(0, (gVal / gMax) * 100));
    gaugeHtml = `
      <div class="gen-gauge-container">
        <svg class="gen-gauge-svg" viewBox="0 0 36 36">
          <path class="gen-gauge-bg" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" />
          <path class="gen-gauge-fill" stroke-dasharray="${gPct}, 100" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" />
        </svg>
        <div class="gen-gauge-text">
          <span class="gen-gauge-val">${gVal}</span>
          <span class="gen-gauge-unit">${data.gauge.unit || '%'}</span>
        </div>
      </div>
    `;
  }

  let sparklineHtml = '';
  if (Array.isArray(data.sparkline) && data.sparkline.length > 1) {
    const pts = data.sparkline;
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
    <div class="gen-ui-card gen-card-telemetry" data-widget-id="${wId}">
      ${this.renderHeader(schema)}
      <div class="gen-card-body">
        ${gaugeHtml}
        <div class="gen-metrics-list">${metricsHtml}</div>
        ${sparklineHtml}
      </div>
      ${this.renderActions(wId, schema.actions)}
    </div>
  `;
}
```

#### Update Strategy (`updateTelemetry`):
Direct DOM mutation of targeted element attributes without re-rendering:
```javascript
updateTelemetry(cardEl, deltaData) {
  if (!cardEl || !deltaData) return;
  if (Array.isArray(deltaData.metrics)) {
    deltaData.metrics.forEach(m => {
      const row = cardEl.querySelector(`.gen-metric-row[data-metric-id="${m.id || m.label}"]`);
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
      const row = cardEl.querySelector(`.gen-metric-row[data-metric-id="${k}"]`);
      if (row) {
        const numVal = typeof v === 'number' ? v : parseFloat(v) || 0;
        const pct = Math.min(100, Math.max(0, numVal));
        const valEl = row.querySelector('.gen-metric-val');
        const fillEl = row.querySelector('.gen-metric-fill');
        if (valEl) valEl.textContent = `${numVal}%`;
        if (fillEl) fillEl.style.width = `${pct}%`;
      }
    });
  }

  if (deltaData.gauge) {
    const gVal = deltaData.gauge.value || 0;
    const gMax = deltaData.gauge.max || 100;
    const gPct = Math.min(100, Math.max(0, (gVal / gMax) * 100));
    const gFill = cardEl.querySelector('.gen-gauge-fill');
    const gValEl = cardEl.querySelector('.gen-gauge-val');
    if (gFill) gFill.setAttribute('stroke-dasharray', `${gPct}, 100`);
    if (gValEl) gValEl.textContent = gVal;
  }
}
```

---

### 3.3 Template 2: `activity_tracker`

#### Structure:
- **Header**: Icon, Title, Status Badge, Dismiss button.
- **Status & Progress Row**: Status badge (`RUNNING`, `QUEUED`, `COMPLETED`, `PAUSED`, `ERROR`) and percentage text.
- **Progress Track**: High-performance animated progress bar (`background: linear-gradient(90deg, var(--cyan), var(--indigo))`).
- **Detail Line**: Current step / sub-task description.
- **Step List (Optional)**: Array of sub-steps with state indicators.
- **Actions Footer**: Buttons (`Pause`, `Cancel`, `Retry`).

#### DOM Generator Code:
```javascript
activity_tracker(schema) {
  const wId = schema.id;
  const data = schema.data || {};
  const progress = Math.min(100, Math.max(0, Number(data.progress) || 0));
  const statusText = data.status || schema.status || 'RUNNING';
  const detailText = data.detail || data.step || 'Processing...';

  let stepsHtml = '';
  if (Array.isArray(data.steps) && data.steps.length > 0) {
    stepsHtml = `<div class="gen-steps-list">` + data.steps.map(step => {
      const isDone = step.completed;
      const isCurrent = step.current;
      const stepClass = isDone ? 'completed' : isCurrent ? 'active' : 'pending';
      return `
        <div class="gen-step-item ${stepClass}">
          <span class="gen-step-dot"></span>
          <span class="gen-step-label">${step.label || step}</span>
        </div>
      `;
    }).join('') + `</div>`;
  }

  return `
    <div class="gen-ui-card gen-card-tracker" data-widget-id="${wId}">
      ${this.renderHeader(schema)}
      <div class="gen-card-body">
        <div class="gen-tracker-status-row">
          <span class="gen-tracker-state-badge status-${statusText.toLowerCase()}">${statusText}</span>
          <span class="gen-tracker-pct">${progress}%</span>
        </div>
        <div class="gen-progress-track">
          <div class="gen-progress-fill" style="width: ${progress}%"></div>
        </div>
        <div class="gen-tracker-detail">${detailText}</div>
        ${stepsHtml}
      </div>
      ${this.renderActions(wId, schema.actions)}
    </div>
  `;
}
```

#### Update Strategy (`updateActivityTracker`):
```javascript
updateActivityTracker(cardEl, deltaData) {
  if (!cardEl || !deltaData) return;
  if (deltaData.progress !== undefined) {
    const pct = Math.min(100, Math.max(0, Number(deltaData.progress) || 0));
    const fill = cardEl.querySelector('.gen-progress-fill');
    const pctEl = cardEl.querySelector('.gen-tracker-pct');
    if (fill) fill.style.width = `${pct}%`;
    if (pctEl) pctEl.textContent = `${pct}%`;
  }
  if (deltaData.status) {
    const badge = cardEl.querySelector('.gen-tracker-state-badge');
    if (badge) {
      badge.className = `gen-tracker-state-badge status-${deltaData.status.toLowerCase()}`;
      badge.textContent = deltaData.status;
    }
  }
  if (deltaData.detail || deltaData.step) {
    const detailEl = cardEl.querySelector('.gen-tracker-detail');
    if (detailEl) detailEl.textContent = deltaData.detail || deltaData.step;
  }
}
```

---

### 3.4 Template 3: `action_grid`

#### Structure:
- **Header**: Icon, Title, optional Meta subtitle, Dismiss button.
- **Control Center Grid**: Multi-column grid of glass action tiles.
- **Tile Variants**:
  1. *Momentary action tile*: Triggers immediate backend action on click.
  2. *Toggle switch tile*: Maintains stateful active/inactive glow and badge ("ON" / "OFF").
  3. *Parameterized tile*: Dispatches embedded JSON payload.

#### DOM Generator Code:
```javascript
action_grid(schema) {
  const wId = schema.id;
  const data = schema.data || {};
  const items = data.items || data.buttons || schema.actions || [];

  const tilesHtml = items.map(item => {
    const actId = item.action_id || item.id;
    const label = item.label || actId;
    const iconSvg = this.getIcon(item.icon || 'zap');
    const isToggle = Boolean(item.toggle);
    const isActive = Boolean(item.active);
    const activeClass = isActive ? ' active' : '';
    const badgeText = item.badge || (isToggle ? (isActive ? 'ON' : 'OFF') : '');
    const badgeHtml = badgeText ? `<span class="gen-tile-badge">${badgeText}</span>` : '';
    const payloadStr = item.payload ? JSON.stringify(item.payload).replace(/"/g, '&quot;') : '{}';

    return `
      <button class="gen-action-tile${activeClass}" 
              data-widget-id="${wId}" 
              data-action-id="${actId}" 
              data-toggle="${isToggle}" 
              data-active="${isActive}" 
              data-payload="${payloadStr}">
        <span class="gen-tile-icon">${iconSvg}</span>
        <span class="gen-tile-label">${label}</span>
        ${badgeHtml}
      </button>
    `;
  }).join('');

  return `
    <div class="gen-ui-card gen-card-action-grid" data-widget-id="${wId}">
      ${this.renderHeader(schema)}
      <div class="gen-card-body">
        <div class="gen-action-grid">${tilesHtml}</div>
      </div>
      ${this.renderActions(wId, schema.actions && schema.actions !== items ? schema.actions : [])}
    </div>
  `;
}
```

#### Update Strategy (`updateActionGrid`):
```javascript
updateActionGrid(cardEl, deltaData) {
  if (!cardEl || !deltaData) return;
  const list = deltaData.items || deltaData.buttons;
  if (Array.isArray(list)) {
    list.forEach(item => {
      const actId = item.action_id || item.id;
      const tile = cardEl.querySelector(`.gen-action-tile[data-action-id="${actId}"]`);
      if (tile) {
        if (item.active !== undefined) {
          tile.dataset.active = item.active;
          if (item.active) tile.classList.add('active');
          else tile.classList.remove('active');
          const badge = tile.querySelector('.gen-tile-badge');
          if (badge && tile.dataset.toggle === 'true') {
            badge.textContent = item.active ? 'ON' : 'OFF';
          }
        }
        if (item.badge !== undefined) {
          let bEl = tile.querySelector('.gen-tile-badge');
          if (!bEl) {
            bEl = document.createElement('span');
            bEl.className = 'gen-tile-badge';
            tile.appendChild(bEl);
          }
          bEl.textContent = item.badge;
        }
      }
    });
  }
}
```

---

## 4. Inbound WebSocket Message Routing in `ui_improved.html`

In `ui_improved.html`, the WebSocket message receiver is defined at lines 1825–1902 (`ws.onmessage = (event) => { ... }`).
Line 1882 currently contains the designated integration marker:
```javascript
// === PUT THEM RIGHT HERE ===
```

### Exact Insertion Code:
```javascript
          // === GENERATIVE UI WEBSOCKET HANDLERS ===
          else if (msg.type === 'widget_render') {
            if (msg.widget && window.widgetManager) {
              window.widgetManager.renderWidget(msg.widget);
            }
          }
          else if (msg.type === 'widget_update') {
            if (msg.widget_id && window.widgetManager) {
              window.widgetManager.updateWidget(msg.widget_id, msg.data || {});
            }
          }
          else if (msg.type === 'widget_dismiss') {
            if (msg.widget_id && window.widgetManager) {
              window.widgetManager.dismissWidget(msg.widget_id);
            }
          }
```

### Resilience Features:
- Null checks on `msg.widget`, `msg.widget_id`, and `window.widgetManager`.
- If `window.widgetManager` is not yet mounted (e.g. late script init), messages fail safely without throwing exceptions or corrupting the WebSocket loop.

---

## 5. Outbound User Action Event Dispatching

### 5.1 Programmatic Dispatch Helper
```javascript
function sendWidgetAction(widgetId, actionId, payload = {}) {
  if (typeof sfx !== 'undefined' && sfx.click) {
    sfx.click();
  }
  const message = {
    type: 'widget_action',
    widget_id: String(widgetId),
    action_id: String(actionId),
    payload: payload || {}
  };

  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(message));
    return true;
  } else {
    console.warn('[WebBridge] Cannot dispatch widget_action; WebSocket offline', message);
    return false;
  }
}
```

### 5.2 Declarative Event Delegation
Instead of attaching individual click listeners to every generated element, we register a single delegated event listener on `document` (or the `#gen-ui-dock` and `#chat-history` containers). This provides:
1. **Zero memory leaks** upon widget dismissal.
2. **Instant reactivity** for dynamically rendered or updated widgets.
3. **Immediate optimistic UI update** for toggle switches.

```javascript
document.addEventListener('click', (event) => {
  const btn = event.target.closest('[data-action-id]');
  if (!btn) return;

  const card = btn.closest('[data-widget-id]');
  const widgetId = btn.dataset.widgetId || (card ? card.dataset.widgetId : null);
  const actionId = btn.dataset.actionId;
  if (!widgetId || !actionId) return;

  // 1. Close/Dismiss button
  if (actionId === 'dismiss') {
    if (window.widgetManager) {
      window.widgetManager.dismissWidget(widgetId);
    }
    sendWidgetAction(widgetId, 'dismiss', { reason: 'user_close' });
    return;
  }

  // 2. Parse payload
  let payload = {};
  try {
    payload = btn.dataset.payload ? JSON.parse(btn.dataset.payload) : {};
  } catch (e) {
    payload = {};
  }

  // 3. Handle stateful toggles
  if (btn.dataset.toggle === 'true') {
    const currentlyActive = btn.dataset.active === 'true' || btn.classList.contains('active');
    const nextActive = !currentlyActive;
    btn.dataset.active = String(nextActive);
    if (nextActive) {
      btn.classList.add('active');
    } else {
      btn.classList.remove('active');
    }
    const badge = btn.querySelector('.gen-tile-badge');
    if (badge) {
      badge.textContent = nextActive ? 'ON' : 'OFF';
    }
    payload.active = nextActive;
  }

  // 4. Dispatch to backend
  sendWidgetAction(widgetId, actionId, payload);
});
```

---

## 6. Integration Contract with Peer Explorers

### Coordination with Explorer 1 (DOM & CSS Styling):
Our templates generate class names matching the styling tokens designed by Explorer 1:
- Container Card: `.gen-ui-card`, `.gen-card-telemetry`, `.gen-card-tracker`, `.gen-card-action-grid`, `.gen-card-custom`
- Header: `.gen-card-header`, `.gen-card-title-group`, `.gen-card-icon`, `.gen-card-title`, `.gen-card-close-btn`
- Status Badges: `.gen-status-badge`, `.gen-tracker-state-badge`
- Metrics: `.gen-metric-row`, `.gen-metric-info`, `.gen-metric-label`, `.gen-metric-val`, `.gen-metric-track`, `.gen-metric-fill`
- Gauge: `.gen-gauge-container`, `.gen-gauge-svg`, `.gen-gauge-bg`, `.gen-gauge-fill`, `.gen-gauge-text`, `.gen-gauge-val`, `.gen-gauge-unit`
- Sparkline: `.gen-sparkline-wrap`, `.gen-sparkline-svg`
- Progress: `.gen-progress-track`, `.gen-progress-fill`, `.gen-tracker-detail`, `.gen-steps-list`, `.gen-step-item`
- Action Grid: `.gen-action-grid`, `.gen-action-tile`, `.gen-tile-icon`, `.gen-tile-label`, `.gen-tile-badge`
- Action Buttons: `.gen-card-actions`, `.gen-action-btn`, `.gen-btn-primary`, `.gen-btn-secondary`, `.gen-btn-danger`, `.gen-btn-outline`

### Coordination with Explorer 2 (WidgetManager Lifecycle):
Explorer 2's `WidgetManager` connects cleanly to `WidgetTemplates`:
```javascript
// In WidgetManager.renderWidget(schema):
const templateName = schema.template || 'custom';
const generator = WidgetTemplates[templateName] || WidgetTemplates.custom;
const html = generator.call(WidgetTemplates, schema);

// In WidgetManager.updateWidget(widgetId, deltaData):
const entry = this.widgets.get(widgetId);
if (entry) {
  const updaters = {
    telemetry: WidgetTemplates.updateTelemetry,
    activity_tracker: WidgetTemplates.updateActivityTracker,
    action_grid: WidgetTemplates.updateActionGrid
  };
  const fn = updaters[entry.template];
  if (fn) fn.call(WidgetTemplates, entry.element, deltaData);
}
```

---

## 7. Verification Results & Test Pass

The entire pytest suite was executed to verify baseline stability and contract conformance:
```powershell
cd C:\jarvis\Mark-LV-main\Mark-LV-main
.\.venv\Scripts\python.exe -m pytest
```
**Result**: `139 passed, 1 skipped, 2 warnings in 12.68s`.
- `tests/test_web_bridge_e2e.py`:
  - `test_generative_ui_interface_contracts_validity`: **PASSED**
  - `test_ws_widget_action_message_tolerance`: **PASSED**
  - `test_scenario_1_full_lifecycle_startup_to_action`: **PASSED**
- Zero regressions on existing test suite.

---

## 8. Summary of Findings

1. `ui_improved.html` has explicit integration points (`ws.onmessage` at lines 1881–1883) for the three inbound message types.
2. The designed `WidgetTemplates` object provides fully featured, lightweight, compositor-safe markup for all three target widget schemas (`telemetry`, `activity_tracker`, `action_grid`).
3. Outbound event dispatching combines event delegation with Web Audio API procedural sound feedback, perfectly harmonizing with the existing desktop voice assistant UX.
