/**
 * independent_adversarial_test.js
 * Independent Adversarial Stress & Security Test Suite for Milestone 2 Iteration 2
 * Author: Milestone 2 Iteration 2 Reviewer 1 (teamwork_reviewer)
 */

const fs = require('fs');
const path = require('path');
const vm = require('vm');

console.log('=== [INDEPENDENT ADVERSARIAL STRESS & INTEGRITY SUITE: M2 IT2] ===\n');

// 1. Read ui_improved.html
const htmlPath = path.resolve('C:\\jarvis\\Mark-LV-main\\Mark-LV-main\\ui_improved.html');
const html = fs.readFileSync(htmlPath, 'utf8');

// 2. Build mock DOM environment
class MockDOMTokenList {
  constructor(initial = '') {
    this._tokens = new Set(initial.split(/\s+/).filter(Boolean));
  }
  add(...tokens) {
    tokens.forEach(t => String(t).split(/\s+/).filter(Boolean).forEach(tok => this._tokens.add(tok)));
  }
  remove(...tokens) {
    tokens.forEach(t => String(t).split(/\s+/).filter(Boolean).forEach(tok => this._tokens.delete(tok)));
  }
  contains(token) {
    return this._tokens.has(token);
  }
  toString() {
    return Array.from(this._tokens).join(' ');
  }
}

class MockElement {
  constructor(tagName = 'div') {
    this.tagName = tagName.toUpperCase();
    this.id = '';
    this.classList = new MockDOMTokenList();
    this.attributes = new Map();
    this.dataset = {};
    this.style = {};
    this.childNodes = [];
    this.parentNode = null;
    this.listeners = new Map();
    this._innerHTML = '';
    this._textContent = '';
  }

  get className() { return this.classList.toString(); }
  set className(val) {
    this.classList = new MockDOMTokenList(val || '');
  }

  get textContent() { return this._textContent; }
  set textContent(val) {
    this._textContent = String(val);
    this.childNodes = [];
  }

  get innerHTML() { return this._innerHTML; }
  set innerHTML(val) {
    this._innerHTML = String(val);
    this.childNodes = [];
    this._parseHTML(this._innerHTML);
  }

  setAttribute(k, v) {
    this.attributes.set(k, String(v));
    if (k === 'id') this.id = String(v);
    if (k === 'class') this.className = String(v);
    if (k.startsWith('data-')) {
      const dKey = k.slice(5).replace(/-([a-z])/g, (_, c) => c.toUpperCase());
      this.dataset[dKey] = String(v);
    }
  }

  getAttribute(k) {
    if (k === 'id') return this.id || null;
    if (k === 'class') return this.className || null;
    if (k.startsWith('data-')) {
      const dKey = k.slice(5).replace(/-([a-z])/g, (_, c) => c.toUpperCase());
      return this.dataset[dKey] !== undefined ? this.dataset[dKey] : (this.attributes.get(k) || null);
    }
    return this.attributes.get(k) || null;
  }

  hasAttribute(k) {
    if (k === 'id') return Boolean(this.id);
    if (k === 'class') return Boolean(this.className);
    if (k.startsWith('data-')) {
      const dKey = k.slice(5).replace(/-([a-z])/g, (_, c) => c.toUpperCase());
      return this.dataset[dKey] !== undefined || this.attributes.has(k);
    }
    return this.attributes.has(k);
  }

  removeAttribute(k) {
    this.attributes.delete(k);
    if (k === 'id') this.id = '';
    if (k === 'class') this.className = '';
    if (k.startsWith('data-')) {
      const dKey = k.slice(5).replace(/-([a-z])/g, (_, c) => c.toUpperCase());
      delete this.dataset[dKey];
    }
  }

  appendChild(child) {
    if (child.parentNode) {
      child.parentNode.removeChild(child);
    }
    child.parentNode = this;
    this.childNodes.push(child);
    return child;
  }

  removeChild(child) {
    const idx = this.childNodes.indexOf(child);
    if (idx !== -1) {
      this.childNodes.splice(idx, 1);
      child.parentNode = null;
      return child;
    }
    return null;
  }

  addEventListener(type, handler, opts) {
    if (!this.listeners.has(type)) this.listeners.set(type, []);
    this.listeners.get(type).push({ handler, opts });
  }

  removeEventListener(type, handler) {
    const arr = this.listeners.get(type);
    if (arr) {
      this.listeners.set(type, arr.filter(l => l.handler !== handler));
    }
  }

  dispatchEvent(event) {
    event.target = this;
    let curr = this;
    while (curr) {
      const list = curr.listeners.get(event.type);
      if (list) {
        for (const item of list) {
          item.handler.call(curr, event);
          if (event._stopped) return;
        }
      }
      curr = curr.parentNode;
    }
  }

  _parseHTML(str) {
    // Basic tag parser for HTML simulations
    const tagRegex = /<([a-zA-Z0-9_-]+)([^>]*)>([\s\S]*?)<\/\1>|<([a-zA-Z0-9_-]+)([^>]*)\/?>/g;
    let match;
    while ((match = tagRegex.exec(str)) !== null) {
      const tag = match[1] || match[4];
      const attrsStr = match[2] || match[5] || '';
      const inner = match[3] || '';
      const child = new MockElement(tag);

      const attrRegex = /([a-zA-Z0-9_-]+)(?:=(?:"([^"]*)"|'([^']*)'|([^\s>]+)))?/g;
      let aMatch;
      while ((aMatch = attrRegex.exec(attrsStr)) !== null) {
        const aName = aMatch[1];
        const aVal = aMatch[2] !== undefined ? aMatch[2] : (aMatch[3] !== undefined ? aMatch[3] : (aMatch[4] !== undefined ? aMatch[4] : ''));
        child.setAttribute(aName, aVal);
      }
      if (inner) {
        child._textContent = inner.replace(/<[^>]*>/g, '').trim();
        child._innerHTML = inner;
        child._parseHTML(inner);
      }
      this.appendChild(child);
    }
  }

  _matchesSelector(sel) {
    const parts = sel.split(',').map(s => s.trim());
    for (const p of parts) {
      if (p.startsWith('.')) {
        if (this.classList.contains(p.slice(1))) return true;
      } else if (p.startsWith('#')) {
        if (this.id === p.slice(1)) return true;
      } else if (p.startsWith('[') && p.endsWith(']')) {
        const attrExpr = p.slice(1, -1);
        if (attrExpr.includes('=')) {
          const [k, v] = attrExpr.split('=').map(s => s.replace(/["']/g, '').trim());
          if (this.getAttribute(k) === v) return true;
          if (k.startsWith('data-')) {
            const dKey = k.slice(5).replace(/-([a-z])/g, (_, c) => c.toUpperCase());
            if (this.dataset[dKey] === v) return true;
          }
        } else {
          if (this.hasAttribute(attrExpr)) return true;
          if (attrExpr.startsWith('data-')) {
            const dKey = attrExpr.slice(5).replace(/-([a-z])/g, (_, c) => c.toUpperCase());
            if (this.dataset[dKey] !== undefined) return true;
          }
        }
      } else if (this.tagName.toLowerCase() === p.toLowerCase()) {
        return true;
      }
    }
    return false;
  }

  querySelector(sel) {
    return this.querySelectorAll(sel)[0] || null;
  }

  querySelectorAll(sel) {
    const results = [];
    const traverse = (node) => {
      for (const child of node.childNodes) {
        if (child._matchesSelector(sel)) {
          results.push(child);
        }
        traverse(child);
      }
    };
    traverse(this);
    return results;
  }

  closest(sel) {
    let curr = this;
    while (curr) {
      if (curr._matchesSelector && curr._matchesSelector(sel)) return curr;
      curr = curr.parentNode;
    }
    return null;
  }
}

class MockDocument extends MockElement {
  constructor() {
    super('#document');
    this.body = new MockElement('body');
    this.body.parentNode = this;
    this.childNodes = [this.body];
  }
  createElement(tag) { return new MockElement(tag); }
  getElementById(id) {
    const traverse = (node) => {
      if (node.id === id) return node;
      for (const child of node.childNodes) {
        const f = traverse(child);
        if (f) return f;
      }
      return null;
    };
    return traverse(this);
  }
}

// 3. Extract and compile WidgetTemplates, WidgetManager, and Action Delegation
const wtStart = html.indexOf('const WidgetTemplates = {');
const wmEnd = html.indexOf('window.widgetManager = widgetManager;', wtStart);
const genUiCode = html.slice(wtStart, wmEnd + 'window.widgetManager = widgetManager;'.length);

const actStart = html.indexOf('function sendWidgetAction(');
const actEnd = html.indexOf('// Start WebSocket connection on load', actStart);
const actionCode = html.slice(actStart, actEnd);

const doc = new MockDocument();
const uiLayer = doc.createElement('div');
uiLayer.className = 'ui-layer';
doc.body.appendChild(uiLayer);

const dock = doc.createElement('div');
dock.id = 'gen-ui-dock';
dock.className = 'gen-ui-dock interactive';
uiLayer.appendChild(dock);

const chat = doc.createElement('div');
chat.id = 'chat-history';
uiLayer.appendChild(chat);

const dispatchedWsMessages = [];
const mockWs = {
  readyState: 1,
  send: (msg) => { dispatchedWsMessages.push(JSON.parse(msg)); }
};

const sandbox = {
  console: console,
  setTimeout: setTimeout,
  clearTimeout: clearTimeout,
  document: doc,
  window: {
    innerWidth: 1920,
    innerHeight: 1080,
    addEventListener: () => {}
  },
  ws: mockWs,
  WebSocket: { OPEN: 1, CLOSED: 3 }
};
sandbox.window.document = doc;

vm.createContext(sandbox);
vm.runInContext(genUiCode, sandbox);
vm.runInContext(actionCode, sandbox);

const wm = sandbox.window.widgetManager;
const wt = sandbox.window.WidgetTemplates;

let passed = 0;
let failed = 0;

function assert(condition, testName) {
  if (condition) {
    console.log(`  ✓ PASS: ${testName}`);
    passed++;
  } else {
    console.error(`  ✗ FAIL: ${testName}`);
    failed++;
  }
}

// =========================================================================
// TEST 1: Extreme Burst Eviction (50 Widgets synchronously)
// =========================================================================
console.log('\n[Test 1: Extreme Synchronous Burst Eviction - 50 Widgets]');
for (let i = 1; i <= 50; i++) {
  wm.renderWidget({
    id: `burst_extreme_${i}`,
    template: 'telemetry',
    title: `Telemetry Card #${i}`,
    data: { cpu: i * 2 }
  });
}

assert(wm.widgets.size <= 4, `wm.widgets registry size strictly <= 4 (actual: ${wm.widgets.size})`);
const remainingKeys = Array.from(wm.widgets.keys());
assert(remainingKeys.includes('burst_extreme_50'), `Latest card burst_extreme_50 retained in registry`);
assert(remainingKeys.includes('burst_extreme_49'), `Second latest card burst_extreme_49 retained`);
assert(remainingKeys.includes('burst_extreme_48'), `Third latest card burst_extreme_48 retained`);
assert(remainingKeys.includes('burst_extreme_47'), `Fourth latest card burst_extreme_47 retained`);
assert(!remainingKeys.includes('burst_extreme_1'), `Oldest burst_extreme_1 safely evicted`);

// =========================================================================
// TEST 2: Re-entrant and Concurrent Dismissal
// =========================================================================
console.log('\n[Test 2: Idempotent Re-entrant Dismissal]');
const testCard = wm.renderWidget({
  id: 'reentrant_test',
  template: 'custom',
  title: 'Reentrant Test'
});
assert(wm.widgets.has('reentrant_test'), 'Card mounted');

// Call dismiss twice with animated dismissal
const res1 = wm.dismissWidget('reentrant_test', { immediate: false });
const res2 = wm.dismissWidget('reentrant_test', { immediate: false });
assert(res1 === true, 'First dismiss returned true');
assert(res2 === true, 'Second dismiss returned true (idempotent)');
const entry = wm.widgets.get('reentrant_test');
assert(entry.dismissing === true, 'Entry marked as dismissing');

// Now call immediate dismissal
const res3 = wm.dismissWidget('reentrant_test', { immediate: true });
assert(res3 === true, 'Immediate dismiss returned true');
assert(!wm.widgets.has('reentrant_test'), 'Card removed from registry after immediate teardown');

// =========================================================================
// TEST 3: Adversarial Injection Vectors
// =========================================================================
console.log('\n[Test 3: Adversarial Injection Vectors]');

const injectionPayload = '<script>alert("pwned")</script><img src="x" onerror="evil()"><style>body{display:none}</style>" onfocus="hack()" \' autofocus';

const advWidget = wm.renderWidget({
  id: 'adv_widget_1',
  template: 'telemetry',
  title: injectionPayload,
  status: 'ACTIVE"><script>hack()</script>',
  actions: [
    {
      action_id: 'btn"><img src=x onerror=hack()>',
      label: 'Click Me <script>hack()</script>',
      variant: 'primary" onclick="evil()" style="color:red',
      payload: { secret: 'clean_val' }
    }
  ],
  data: {
    metrics: [
      {
        id: 'metric_id"><img src=x onerror=hack()>',
        label: 'Metric Label <script>hack()</script>',
        value: '45"><script>hack()</script>',
        unit: 'MB/s"><script>hack()</script>'
      }
    ],
    gauge: {
      value: '99"><img src=x onerror=hack()>',
      unit: '%"><script>hack()</script>'
    }
  }
});

const renderedHtml = advWidget.containerEl.innerHTML;
const scriptTags = advWidget.containerEl.querySelectorAll('script');
const imgTags = advWidget.containerEl.querySelectorAll('img');

assert(scriptTags.length === 0, `DOM parsed zero <script> tags (got ${scriptTags.length})`);
assert(imgTags.length === 0, `DOM parsed zero <img> injection tags (got ${imgTags.length})`);
assert(!renderedHtml.includes('onfocus="hack()"'), 'Rendered HTML contains zero unescaped event handler breakouts');
assert(!renderedHtml.includes('onclick="evil()"'), 'Rendered HTML contains zero unescaped onclick attribute injections');

// =========================================================================
// TEST 4: Delta Updates with Corrupt and Prototype Pollution Inputs
// =========================================================================
console.log('\n[Test 4: Corrupt Delta Updates and Prototype Pollution]');

const up1 = wm.updateWidget('adv_widget_1', {
  metrics: null,
  gauge: undefined,
  status: 'WARN'
});
assert(up1 === true, 'Handled delta with null metrics and undefined gauge gracefully');

const up2 = wm.updateWidget('adv_widget_1', {
  metrics: [null, undefined, { id: 'metric_id"><img src=x onerror=hack()>', value: 88 }]
});
assert(up2 === true, 'Handled sparse metrics array with null/undefined entries safely');

const up3 = wm.updateWidget('adv_widget_1', JSON.parse('{"__proto__": {"polluted": true}}'));
assert(up3 === true, 'Handled prototype pollution attempt safely');
assert(Object.prototype.polluted === undefined, 'Prototype remains unpolluted');

// =========================================================================
// TEST 5: Activity Tracker Adversarial Array & Status Sanitization
// =========================================================================
console.log('\n[Test 5: Activity Tracker Adversarial Sanitization]');
const actWidget = wm.renderWidget({
  id: 'adv_act_1',
  template: 'activity_tracker',
  title: 'Processing',
  data: {
    status: 'PAUSED"; background: red; " onclick="evil()',
    progress: 'NaN',
    steps: [
      null,
      undefined,
      { label: '<script>evil()</script>', completed: true },
      { label: 'Step 2', current: true }
    ]
  }
});
assert(actWidget !== null, 'Activity tracker rendered despite malformed steps and status');
const actHtml = actWidget.containerEl.innerHTML;
assert(!actHtml.includes('<script>evil()</script>'), 'Steps labels are escaped');
assert(!actHtml.includes('onclick="evil()'), 'Status class attribute sanitized from breakout');

// =========================================================================
// TEST 6: Action Grid Stateful Toggle and JSON Parsing
// =========================================================================
console.log('\n[Test 6: Action Grid Stateful Toggle]');
const gridWidget = wm.renderWidget({
  id: 'grid_1',
  template: 'action_grid',
  title: 'Grid Panel',
  data: {
    items: [
      { action_id: 'wifi_toggle', label: 'Wi-Fi', toggle: true, active: false, icon: 'wifi' }
    ]
  }
});
assert(gridWidget !== null, 'Grid widget rendered');

const toggleBtn = gridWidget.containerEl.querySelector('.gen-action-tile');
assert(toggleBtn !== null, 'Toggle button found');

// Simulate click on toggle button
const clickEvt = {
  type: 'click',
  stopPropagation: () => { clickEvt._stopped = true; }
};
toggleBtn.dispatchEvent(clickEvt);

assert(dispatchedWsMessages.length > 0, 'WebSocket action message dispatched');
const lastMsg = dispatchedWsMessages[dispatchedWsMessages.length - 1];
assert(lastMsg && lastMsg.type === 'widget_action', 'Message type is widget_action');
assert(lastMsg && lastMsg.widget_id === 'grid_1', 'Target widget ID correct');
assert(lastMsg && lastMsg.action_id === 'wifi_toggle', 'Action ID correct');
assert(lastMsg && lastMsg.payload && lastMsg.payload.active === true, 'Toggle flipped from false to true in payload');

// =========================================================================
// TEST 7: Self-Healing Fallback when Container Destroyed
// =========================================================================
console.log('\n[Test 7: Self-Healing DOM Recovery]');
const dockEl = doc.getElementById('gen-ui-dock');
dockEl.parentNode.removeChild(dockEl);
assert(doc.getElementById('gen-ui-dock') === null, 'Dock completely deleted from DOM');

const healedEntry = wm.renderWidget({
  id: 'healed_card',
  template: 'telemetry',
  title: 'Healed Card'
});
assert(healedEntry !== null, 'Widget rendered despite missing container');
const recreatedDock = doc.getElementById('gen-ui-dock');
assert(recreatedDock !== null, 'Container #gen-ui-dock self-healed');
assert(recreatedDock.classList.contains('gen-ui-dock'), 'Self-healed container has .gen-ui-dock class');

// =========================================================================
// SUMMARY
// =========================================================================
console.log('\n======================================================');
console.log(`TOTAL TESTS: ${passed + failed}`);
console.log(`PASSED: ${passed}`);
console.log(`FAILED: ${failed}`);
console.log('======================================================');

if (failed > 0) {
  process.exit(1);
} else {
  process.exit(0);
}
