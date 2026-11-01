// Test script for verifying hardened WidgetTemplates and _generateHtml
const assert = require('assert');

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
        const row = Array.from(cardEl.querySelectorAll('.gen-metric-row')).find(
          r => r.dataset.metricId === metricId || r.getAttribute('data-metric-id') === metricId
        );
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
        const row = Array.from(cardEl.querySelectorAll('.gen-metric-row')).find(
          r => r.dataset.metricId === k || r.getAttribute('data-metric-id') === k
        );
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

// Simulation of _generateHtml
function generateHtml(schema, widgetId, templateName, templatesMap = new Map()) {
  try {
    const tplDef = templatesMap.get(templateName);
    if (tplDef && typeof tplDef.render === 'function') {
      return tplDef.render(schema);
    }
    if (typeof WidgetTemplates[templateName] === 'function') {
      return WidgetTemplates[templateName](schema);
    }
    const safeTitle = WidgetTemplates._escape(schema.title || widgetId);
    return `<div class="gen-ui-card"><div class="gen-ui-title">${safeTitle}</div></div>`;
  } catch (err) {
    console.error(`[WidgetManager] Error rendering template '${templateName}' for widget '${widgetId}':`, err);
    const safeId = WidgetTemplates._escape(schema && schema.title ? schema.title : widgetId);
    const safeMsg = WidgetTemplates._escape(err && err.message ? err.message : 'Render Error');
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

// ---------------------------------------------------------------------------
// Run Verification Tests
// ---------------------------------------------------------------------------
console.log('Testing Adversarial Injections...');

// 1. Metric ID Injection
const pocBreakout = 'metric"><img src=x onerror=alert(1)>';
const telemetryHtml = WidgetTemplates.telemetry({
  id: 'test_poc',
  template: 'telemetry',
  title: 'Safe Title',
  data: {
    metrics: [{ label: pocBreakout, value: 42, unit: '%' }]
  }
});
assert(!telemetryHtml.includes('<img src=x onerror=alert(1)>'), 'FAIL: Metric ID injection escaped');
assert(telemetryHtml.includes('&quot;&gt;&lt;img src=x onerror=alert(1)&gt;'), 'PASS: Metric ID properly entity-escaped');
console.log('✓ PASS: Metric ID injection neutralized');

// 2. Gauge Value Injection
const gaugeValPoc = '<img src=x onerror=alert(2)>';
const gaugeHtml = WidgetTemplates.telemetry({
  id: 'test_gauge',
  template: 'telemetry',
  data: { gauge: { value: gaugeValPoc } }
});
assert(!gaugeHtml.includes('<img src=x onerror=alert(2)>'), 'FAIL: Gauge value injection escaped');
assert(gaugeHtml.includes('&lt;img src=x onerror=alert(2)&gt;'), 'PASS: Gauge value properly entity-escaped');
console.log('✓ PASS: Gauge value injection neutralized');

// 3. Action Variant Injection
const actionVariantPoc = 'primary" onfocus="alert(3)';
const actionHtml = WidgetTemplates.telemetry({
  id: 'test_act',
  template: 'telemetry',
  actions: [{ id: 'b1', label: 'Click', variant: actionVariantPoc }]
});
assert(!actionHtml.includes('class="gen-ui-btn primary" onfocus="alert(3)"'), 'FAIL: Action variant injection escaped');
assert(actionHtml.includes('class="gen-ui-btn primary&quot; onfocus=&quot;alert(3)"'), 'PASS: Action variant properly entity-escaped');
console.log('✓ PASS: Action variant injection neutralized');

// 4. Status Text Attribute Breakout
const statusPoc = 'running" onmouseover="alert(4)';
const trackerHtml = WidgetTemplates.activity_tracker({
  id: 'test_tracker',
  template: 'activity_tracker',
  data: { status: statusPoc }
});
assert(!trackerHtml.includes('status-running" onmouseover='), 'FAIL: Status class breakout');
assert(trackerHtml.includes('status-runningonmouseoveralert4'), 'PASS: Status class sanitized to safe tokens');
console.log('✓ PASS: Status class breakout neutralized');

// 5. Sparse & Null Array Handling
console.log('\nTesting Sparse & Null Arrays...');
// Telemetry with null metric
assert.doesNotThrow(() => {
  WidgetTemplates.telemetry({ id: 't1', data: { metrics: [null, undefined, 42, { label: 'CPU', value: 80 }] } });
}, 'Telemetry must not throw on null metrics');
console.log('✓ PASS: Telemetry handles sparse/null metrics array');

// Activity tracker with null step
assert.doesNotThrow(() => {
  WidgetTemplates.activity_tracker({ id: 'a1', data: { steps: [null, undefined, { label: 'Step 1', completed: true }] } });
}, 'Activity tracker must not throw on null steps');
console.log('✓ PASS: Activity tracker handles sparse/null steps array');

// Action grid with null item
assert.doesNotThrow(() => {
  WidgetTemplates.action_grid({ id: 'g1', data: { items: [null, undefined, { action_id: 'btn1', label: 'Start' }] } });
}, 'Action grid must not throw on null items');
console.log('✓ PASS: Action grid handles sparse/null items array');

// Render actions with null action
assert.doesNotThrow(() => {
  WidgetTemplates.renderActions('w1', [null, undefined, { action_id: 'a1', label: 'OK' }]);
}, 'renderActions must not throw on null actions');
console.log('✓ PASS: renderActions handles sparse/null actions array');

// 6. _generateHtml Fallback Error Card
console.log('\nTesting _generateHtml Fallback Error Card...');
const brokenTemplates = new Map();
brokenTemplates.set('broken_tpl', {
  render: () => { throw new Error('Crash in custom renderer'); }
});

const errCard = generateHtml({ id: 'bad_w', title: 'Broken Widget' }, 'bad_w', 'broken_tpl', brokenTemplates);
assert(errCard.includes('gen-ui-badge danger'), 'Fallback error card includes danger badge');
assert(errCard.includes('ERROR'), 'Fallback error card has ERROR text');
assert(errCard.includes('Crash in custom renderer'), 'Fallback error card shows error message');
assert(errCard.includes('data-action-id="dismiss"'), 'Fallback error card has dismiss button');
console.log('✓ PASS: _generateHtml gracefully catches template crash and returns error card');

console.log('\n======================================');
console.log('ALL VERIFICATION TESTS PASSED SUCCESSFULLY!');
console.log('======================================');
