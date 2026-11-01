// Independent Adversarial & Integrity Audit Script for Milestone 2 Iteration 2
// Author: Milestone 2 Iteration 2 Reviewer 2 (teamwork_reviewer_m2_it2_2)

const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert');

console.log('=== [INDEPENDENT ADVERSARIAL & SECURITY AUDIT: M2-IT2] ===\n');

const htmlPath = path.resolve('C:/jarvis/Mark-LV-main/Mark-LV-main/ui_improved.html');
const html = fs.readFileSync(htmlPath, 'utf8');

// ---------------------------------------------------------------------------
// 1. Static Anti-Cheat & Code Pattern Audit
// ---------------------------------------------------------------------------
console.log('--- 1. STATIC ANTI-CHEAT & INTEGRITY VERIFICATION ---');

// Check 1.1: Ensure no hardcoded test outputs or fake success strings in ui_improved.html
assert(!html.includes('ALL ORACLE TESTS COMPLETED'), 'FAIL: Hardcoded oracle test output in ui_improved.html');
assert(!html.includes('Burst FIFO maintained capacity'), 'FAIL: Hardcoded test message in ui_improved.html');
assert(!html.includes('test_widget_manager_oracle'), 'FAIL: Test script reference inside production UI code');

// Check 1.2: Verify complete absence of backdrop-filter blur (compositor safety)
const hasBackdropBlur = /backdrop-filter:\s*blur/i.test(html);
assert(!hasBackdropBlur, 'CRITICAL HAZARD: backdrop-filter: blur found in ui_improved.html');
console.log('✓ PASS: Zero hardcoded test outputs. Zero backdrop-filter blur.');

// Check 1.3: Verify offsetWidth is absent from _pulseElement
const pulseMatch = html.match(/_pulseElement\s*\([^)]*\)\s*\{([^}]+)\}/s);
assert(pulseMatch, 'Could not locate _pulseElement in ui_improved.html');
assert(!pulseMatch[1].includes('offsetWidth'), 'CRITICAL: offsetWidth layout thrashing found in _pulseElement');
console.log('✓ PASS: _pulseElement is free of synchronous layout reflow (offsetWidth absent).');

// ---------------------------------------------------------------------------
// 2. Extract and Sandbox JavaScript Engine
// ---------------------------------------------------------------------------
console.log('\n--- 2. JS ENGINE SANDBOX INITIALIZATION ---');
const startToken = 'const WidgetTemplates =';
const endToken = 'window.widgetManager = widgetManager;';
const startIndex = html.indexOf(startToken);
const endIndex = html.indexOf(endToken, startIndex) + endToken.length;

if (startIndex === -1 || endIndex === -1) {
  throw new Error('Failed to locate WidgetTemplates or WidgetManager in ui_improved.html');
}

const jsCode = html.slice(startIndex, endIndex);

class MockElement {
  constructor(tag = 'div') {
    this.tagName = tag.toUpperCase();
    this.classList = {
      _classes: new Set(),
      add(...cs) { cs.forEach(c => c && c.split(/\s+/).forEach(tok => this._classes.add(tok))); },
      remove(...cs) { cs.forEach(c => this._classes.delete(c)); },
      contains(c) { return this._classes.has(c); }
    };
    this.parentNode = null;
    this.children = [];
    this.dataset = {};
    this.attributes = new Map();
    this.style = {};
    this._innerHTML = '';
    this._textContent = '';
    this.listeners = new Map();
  }

  get innerHTML() { return this._innerHTML; }
  set innerHTML(val) {
    this._innerHTML = String(val);
    this._parseChildren(this._innerHTML);
  }

  get textContent() { return this._textContent; }
  set textContent(val) {
    this._textContent = String(val);
    this.children = [];
  }

  get className() { return Array.from(this.classList._classes).join(' '); }
  set className(val) {
    this.classList._classes.clear();
    if (val) this.classList.add(val);
  }

  appendChild(c) {
    c.parentNode = this;
    this.children.push(c);
    return c;
  }

  removeChild(c) {
    const idx = this.children.indexOf(c);
    if (idx !== -1) {
      this.children.splice(idx, 1);
      c.parentNode = null;
    }
    return c;
  }

  setAttribute(name, val) {
    this.attributes.set(name.toLowerCase(), String(val));
    if (name.toLowerCase().startsWith('data-')) {
      const prop = name.slice(5).replace(/-([a-z])/g, (_, ch) => ch.toUpperCase());
      this.dataset[prop] = String(val);
    }
  }

  getAttribute(name) {
    return this.attributes.get(name.toLowerCase()) || null;
  }

  addEventListener(type, handler, opts) {
    if (!this.listeners.has(type)) this.listeners.set(type, []);
    this.listeners.get(type).push({ handler, opts });
  }

  removeEventListener(type, handler) {
    if (!this.listeners.has(type)) return;
    const arr = this.listeners.get(type);
    const i = arr.findIndex(x => x.handler === handler);
    if (i !== -1) arr.splice(i, 1);
  }

  querySelector(sel) {
    return this.querySelectorAll(sel)[0] || null;
  }

  querySelectorAll(sel) {
    const res = [];
    const walk = (node) => {
      for (const child of node.children) {
        if (child._matches(sel)) res.push(child);
        walk(child);
      }
    };
    walk(this);
    return res;
  }

  _matches(sel) {
    const s = sel.trim();
    if (s.startsWith('.')) return this.classList.contains(s.slice(1));
    if (s.startsWith('#')) return this.id === s.slice(1);
    if (s.startsWith('[data-metric-id]')) return this.dataset.metricId !== undefined || this.attributes.has('data-metric-id');
    if (s.startsWith('[data-bind]')) return this.dataset.bind !== undefined;
    if (s === 'button') return this.tagName === 'BUTTON';
    return false;
  }

  _parseChildren(htmlStr) {
    this.children = [];
    const tagRegex = /<([a-z0-9_-]+)([^>]*)>(.*?)<\/\1>|<([a-z0-9_-]+)([^>]*)\/>/gis;
    let match;
    while ((match = tagRegex.exec(htmlStr)) !== null) {
      const tag = match[1] || match[4];
      const attrs = match[2] || match[5] || '';
      const inner = match[3] || '';
      const el = new MockElement(tag);

      const attrRegex = /([a-z0-9_:-]+)(?:=(?:"([^"]*)"|'([^']*)'|([^\s>]+)))?/gi;
      let a;
      while ((a = attrRegex.exec(attrs)) !== null) {
        const k = a[1].toLowerCase();
        const v = a[2] !== undefined ? a[2] : (a[3] !== undefined ? a[3] : (a[4] !== undefined ? a[4] : ''));
        el.setAttribute(k, v);
      }
      el.innerHTML = inner;
      this.appendChild(el);
    }
  }
}

function createSandbox() {
  const dock = new MockElement('div');
  dock.id = 'gen-ui-dock';
  const chat = new MockElement('div');
  chat.id = 'chat-history';
  const body = new MockElement('body');
  body.appendChild(dock);
  body.appendChild(chat);

  const mockDoc = {
    createElement: (t) => new MockElement(t),
    getElementById: (id) => (id === 'gen-ui-dock' ? dock : id === 'chat-history' ? chat : null),
    querySelector: (sel) => (sel === '#gen-ui-dock' ? dock : sel === '#chat-history' ? chat : null),
    body: body
  };

  const sb = {
    window: {},
    document: mockDoc,
    console: console,
    setTimeout: (fn, ms) => 1,
    clearTimeout: () => {},
    Date: Date,
    Math: Math,
    Map: Map,
    Set: Set,
    Array: Array,
    Object: Object,
    String: String,
    Number: Number,
    JSON: JSON
  };
  sb.window = sb;
  vm.createContext(sb);
  vm.runInContext(jsCode, sb);
  return { sb, dock, chat };
}

const { sb: baseSb } = createSandbox();
const WT = baseSb.WidgetTemplates;
const WM = baseSb.window.widgetManager;

// ---------------------------------------------------------------------------
// 3. Adversarial Attack Surface: DOM Injection Testing
// ---------------------------------------------------------------------------
console.log('\n--- 3. ADVERSARIAL DOM INJECTION TESTS ---');

const breakoutPayloads = [
  '<script>alert("xss")</script>',
  '"><script>alert(1)</script>',
  '\'><script>alert(2)</script>',
  '"><img src=x onerror=alert(3)>',
  '\' onfocus=\'alert(4)\'',
  'primary" onfocus="alert(3)',
  'primary" onclick="alert(4)',
  '<svg/onload=alert(6)>',
  '"><iframe src="javascript:alert(7)"></iframe>'
];

// Helper to detect if an injected string managed to produce an unescaped tag or attribute breakout
function hasUnescapedBreakout(htmlSnippet) {
  // Check for unescaped active tag injection
  if (/<(script|img|iframe|object|embed)/i.test(htmlSnippet)) return true;
  // If svg is present, ensure no onload or malicious event attributes
  const svgMatches = htmlSnippet.match(/<svg\b[^>]*>/gi) || [];
  for (const svgTag of svgMatches) {
    if (/\bon[a-z]+\s*=/i.test(svgTag)) return true;
  }
  // Check for unescaped event handler breakout on button/div tags
  if (/<[a-z0-9_-]+[^>]*\s(on[a-z]+)=["'][^"']*["']/i.test(htmlSnippet)) {
    return true;
  }
  return false;
}

// Test 3.1: Metric ID Breakout in Telemetry
console.log('Testing Metric ID Breakout in telemetry template...');
breakoutPayloads.forEach((payload, idx) => {
  const htmlOut = WT.telemetry({
    id: `sec_test_${idx}`,
    template: 'telemetry',
    title: 'Security Probe',
    data: {
      metrics: [
        { id: payload, label: payload, value: 50, unit: '%' }
      ]
    }
  });

  assert(!hasUnescapedBreakout(htmlOut), `VULNERABILITY: Breakout detected in telemetry metrics with payload: ${payload}`);
  // Confirm data-metric-id contains escaped quotes
  if (payload.includes('"')) {
    assert(htmlOut.includes('&quot;'), `Missing &quot; escaping in data-metric-id for payload: ${payload}`);
  }
});
console.log('✓ PASS: All Metric ID breakout attempts neutralized.');

// Test 3.2: Object Keys Breakout in Telemetry
console.log('Testing Object Key Breakout in telemetry template...');
breakoutPayloads.forEach((payload, idx) => {
  const dynamicData = {};
  dynamicData[payload] = 75;
  const htmlOut = WT.telemetry({
    id: `sec_key_${idx}`,
    template: 'telemetry',
    data: dynamicData
  });
  assert(!hasUnescapedBreakout(htmlOut), `VULNERABILITY: Breakout detected in telemetry key with payload: ${payload}`);
});
console.log('✓ PASS: All Object Key breakout attempts neutralized.');

// Test 3.3: Gauge Value Tag Injection
console.log('Testing Gauge Value Injection in telemetry template...');
breakoutPayloads.forEach((payload, idx) => {
  const htmlOut = WT.telemetry({
    id: `sec_gauge_${idx}`,
    template: 'telemetry',
    data: { gauge: { value: payload, max: 100, unit: '%' } }
  });
  assert(!hasUnescapedBreakout(htmlOut), `VULNERABILITY: Breakout detected in gauge value with payload: ${payload}`);
});
console.log('✓ PASS: All Gauge Value tag injection attempts neutralized.');

// Test 3.4: Action Button Variant Breakout
console.log('Testing Action Button Variant attribute breakout...');
breakoutPayloads.forEach((payload, idx) => {
  const htmlOut = WT.renderActions('widget_sec', [
    { action_id: `act_${idx}`, label: 'Action', variant: payload }
  ]);
  assert(!hasUnescapedBreakout(htmlOut), `VULNERABILITY: Breakout detected in action button variant with payload: ${payload}`);
  if (payload.includes('"')) {
    assert(htmlOut.includes('&quot;'), `Missing &quot; escaping in action variant for payload: ${payload}`);
  }
});
console.log('✓ PASS: All Action Button variant breakout attempts neutralized.');

// Test 3.5: Status Badge Class Breakout
console.log('Testing Status Badge Class Breakout in renderHeader & activity_tracker...');
breakoutPayloads.forEach((payload, idx) => {
  const headerHtml = WT.renderHeader({
    title: payload,
    status: payload
  });
  assert(!hasUnescapedBreakout(headerHtml), `VULNERABILITY: Breakout detected in header status with payload: ${payload}`);

  const trackerHtml = WT.activity_tracker({
    id: `track_${idx}`,
    title: payload,
    data: { status: payload, progress: 50, detail: payload }
  });
  assert(!hasUnescapedBreakout(trackerHtml), `VULNERABILITY: Breakout detected in activity_tracker status with payload: ${payload}`);
  // Status class in activity_tracker should only contain safe tokens
  const match = trackerHtml.match(/class="gen-tracker-state-badge status-([^"]*)"/);
  assert(match, 'gen-tracker-state-badge missing in tracker HTML');
  const classVal = match[1];
  assert(/^[a-z0-9_-]*$/.test(classVal), `Unsanitized characters in status class: ${classVal}`);
});
console.log('✓ PASS: All Status Badge class breakout attempts neutralized.');

// ---------------------------------------------------------------------------
// 4. Sparse and Corrupted Array Stress Testing
// ---------------------------------------------------------------------------
console.log('\n--- 4. SPARSE AND CORRUPTED ARRAY RESILIENCE ---');

// Test 4.1: Corrupted metrics array
const corruptTelemetry = WT.telemetry({
  id: 'corrupt_telem',
  template: 'telemetry',
  data: {
    metrics: [null, undefined, 42, "string", {}, { id: null, value: undefined }, { label: 'Valid', value: 30 }]
  }
});
assert(corruptTelemetry.includes('gen-metric-row'), 'Should render the valid metric item without crashing');
console.log('✓ PASS: Corrupted metrics array handled gracefully.');

// Test 4.2: Corrupted steps array in activity tracker
const corruptTracker = WT.activity_tracker({
  id: 'corrupt_track',
  template: 'activity_tracker',
  data: {
    steps: [null, undefined, false, { label: 'Step 1', completed: true }, null]
  }
});
assert(corruptTracker.includes('gen-step-item'), 'Should render valid step item without crashing');
console.log('✓ PASS: Corrupted steps array in activity tracker handled gracefully.');

// Test 4.3: Corrupted actions and items in action grid
const corruptGrid = WT.action_grid({
  id: 'corrupt_grid',
  template: 'action_grid',
  data: {
    items: [null, undefined, "not an object", { action_id: 'btn1', label: 'Action 1' }, null]
  },
  actions: [null, { action_id: 'btn2', label: 'Action 2' }]
});
assert(corruptGrid.includes('gen-action-tile'), 'Should render valid action tiles without crashing');
console.log('✓ PASS: Corrupted action grid items handled gracefully.');

// Test 4.4: Corrupted delta updates
const mockCard = new MockElement('div');
mockCard.innerHTML = corruptTelemetry;
WT.updateTelemetry(mockCard, {
  metrics: [null, undefined, { id: 'Valid', value: 88 }]
});
WT.updateActivityTracker(mockCard, {
  progress: null,
  status: null,
  detail: null
});
WT.updateActionGrid(mockCard, {
  items: [null, undefined, { action_id: 'btn1', active: true }]
});
console.log('✓ PASS: Sparse/null delta updates handled without exception.');

// ---------------------------------------------------------------------------
// 5. Burst FIFO Eviction & Dock Capacity Stress Harness
// ---------------------------------------------------------------------------
console.log('\n--- 5. BURST FIFO CAPACITY AUDIT (Capacity <= 4) ---');

const { sb: burstSb, dock: burstDock } = createSandbox();
const burstWm = burstSb.window.widgetManager;

// Rapid burst of 25 widgets
const BURST_COUNT = 25;
for (let i = 1; i <= BURST_COUNT; i++) {
  burstWm.renderWidget({
    id: `stress_card_${i}`,
    template: 'telemetry',
    target: 'dock',
    title: `Card ${i}`,
    data: { status: 'LIVE', cpu: i }
  });
  // Active registry must NEVER exceed maxDockWidgets (4)
  assert(
    burstWm.widgets.size <= 4,
    `VIOLATION: burstWm.widgets.size = ${burstWm.widgets.size} exceeded capacity 4 during iteration ${i}`
  );
}
console.log(`Registry size after ${BURST_COUNT} rapid burst additions: ${burstWm.widgets.size} (Max: ${burstWm.maxDockWidgets})`);
assert(burstWm.widgets.size === 4, `Expected exactly 4 widgets in registry, got ${burstWm.widgets.size}`);

// Verify that the 4 remaining widgets in the registry are the latest 4
const expectedIds = [
  `stress_card_${BURST_COUNT - 3}`,
  `stress_card_${BURST_COUNT - 2}`,
  `stress_card_${BURST_COUNT - 1}`,
  `stress_card_${BURST_COUNT}`
];
for (const id of expectedIds) {
  assert(burstWm.widgets.has(id), `Expected latest card ${id} to be in registry`);
}
console.log('✓ PASS: Burst FIFO accurately evicted oldest 21 widgets and preserved latest 4.');

// ---------------------------------------------------------------------------
// 6. High-Frequency _pulseElement Layout Throttling Audit
// ---------------------------------------------------------------------------
console.log('\n--- 6. REFLOW THROTTLING (_pulseElement) AUDIT ---');

const pulseCard = new MockElement('div');
// Fire 1000 synchronous pulses in tight loop
for (let i = 0; i < 1000; i++) {
  burstWm._pulseElement(pulseCard);
}
assert(pulseCard.classList.contains('gen-ui-pulse'), 'Pulse class should be active on element');
console.log('✓ PASS: 1000 synchronous pulses handled with O(1) class throttling and 0 layout thrashing.');

console.log('\n======================================================');
console.log('ALL INDEPENDENT ADVERSARIAL & SECURITY CHECKS PASSED');
console.log('======================================================\n');
