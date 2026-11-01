/**
 * tests/test_m4_challenger2_oracle.js
 *
 * Milestone 4 Phase 2 Challenger 2: White-Box Adversarial Coverage Hardening Suite.
 * Deeply stress-tests:
 * 1. DOM Saturation Burst Eviction (1,000 widgets burst loop, variable maxDockWidgets limits).
 * 2. Deep Event Propagation & Click Delegation (nested SVG paths, text spans, badges, stateful toggles, payload parsing).
 * 3. Template Exception Boundaries & Fallback Error Cards (custom template render/update errors, escaping, error dismissal).
 * 4. Multi-Template XSS & Injection Sanitization (telemetry, activity_tracker, action_grid, custom).
 * 5. Malformed Payloads & Null Boundary Tolerance (null metrics, broken sparklines, non-object steps).
 * 6. WebSocket Offline & Disconnected Bridge Resilience.
 */

const fs = require('fs');
const path = require('path');
const vm = require('vm');

// ---------------------------------------------------------------------------
// 1. DOM TokenList and MockElement Implementation
// ---------------------------------------------------------------------------

class MockDOMTokenList {
  constructor() {
    this._tokens = new Set();
  }
  add(...tokens) {
    tokens.forEach(t => {
      if (typeof t === 'string') {
        t.split(/\s+/).filter(Boolean).forEach(tok => this._tokens.add(tok));
      }
    });
  }
  remove(...tokens) {
    tokens.forEach(t => {
      if (typeof t === 'string') {
        t.split(/\s+/).filter(Boolean).forEach(tok => this._tokens.delete(tok));
      }
    });
  }
  contains(token) {
    return this._tokens.has(token);
  }
  toggle(token, force) {
    if (force !== undefined) {
      if (force) this.add(token);
      else this.remove(token);
      return force;
    }
    if (this.contains(token)) {
      this.remove(token);
      return false;
    } else {
      this.add(token);
      return true;
    }
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

  get className() {
    return this.classList.toString();
  }

  set className(val) {
    this.classList = new MockDOMTokenList();
    if (val) this.classList.add(val);
  }

  get textContent() {
    return this._textContent;
  }

  set textContent(val) {
    this._textContent = String(val);
    this.childNodes = [];
  }

  get innerHTML() {
    return this._innerHTML;
  }

  set innerHTML(val) {
    this._innerHTML = String(val);
    this._parseHTML(this._innerHTML);
  }

  _parseHTML(html) {
    this.childNodes = [];
    const tagRegex = /<([a-z0-9_-]+)([^>]*)>(.*?)<\/\1>|<([a-z0-9_-]+)([^>]*)\/>/gis;
    let match;
    while ((match = tagRegex.exec(html)) !== null) {
      const tag = match[1] || match[4];
      const attrsStr = match[2] || match[5] || '';
      const inner = match[3] || '';
      const child = new MockElement(tag);

      const attrRegex = /([a-z0-9_:-]+)(?:=(?:"([^"]*)"|'([^']*)'|([^\s>]+)))?/gi;
      let aMatch;
      while ((aMatch = attrRegex.exec(attrsStr)) !== null) {
        const k = aMatch[1].toLowerCase();
        const v = aMatch[2] !== undefined ? aMatch[2] : (aMatch[3] !== undefined ? aMatch[3] : (aMatch[4] !== undefined ? aMatch[4] : ''));
        child.setAttribute(k, v);
      }
      child.innerHTML = inner;
      this.appendChild(child);
    }
  }

  setAttribute(name, value) {
    const k = name.toLowerCase();
    const v = String(value);
    this.attributes.set(k, v);
    if (k === 'id') this.id = v;
    if (k === 'class') this.className = v;
    if (k.startsWith('data-')) {
      const dataKey = k.slice(5).replace(/-([a-z])/g, (_, c) => c.toUpperCase());
      this.dataset[dataKey] = v;
    }
  }

  getAttribute(name) {
    return this.attributes.get(name.toLowerCase()) || null;
  }

  hasAttribute(name) {
    return this.attributes.has(name.toLowerCase());
  }

  removeAttribute(name) {
    const k = name.toLowerCase();
    this.attributes.delete(k);
    if (k === 'id') this.id = '';
    if (k === 'class') this.className = '';
    if (k.startsWith('data-')) {
      const dataKey = k.slice(5).replace(/-([a-z])/g, (_, c) => c.toUpperCase());
      delete this.dataset[dataKey];
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
    }
    return child;
  }

  after(newSibling) {
    if (!this.parentNode) return;
    const siblings = this.parentNode.childNodes;
    const idx = siblings.indexOf(this);
    if (idx !== -1) {
      newSibling.parentNode = this.parentNode;
      siblings.splice(idx + 1, 0, newSibling);
    }
  }

  addEventListener(type, handler, options) {
    if (!this.listeners.has(type)) {
      this.listeners.set(type, []);
    }
    this.listeners.get(type).push({ handler, options });
  }

  removeEventListener(type, handler) {
    if (!this.listeners.has(type)) return;
    const list = this.listeners.get(type);
    const idx = list.findIndex(item => item.handler === handler);
    if (idx !== -1) list.splice(idx, 1);
  }

  dispatchEvent(event) {
    event.target = this;
    if (!event.stopPropagation) event.stopPropagation = () => { event._stopped = true; };
    if (!event.preventDefault) event.preventDefault = () => { event._defaultPrevented = true; };
    let curr = this;
    while (curr) {
      const list = curr.listeners.get(event.type) || [];
      for (const item of [...list]) {
        item.handler.call(curr, event);
        if (item.options && item.options.once) {
          curr.removeEventListener(event.type, item.handler);
        }
        if (event._stopped) return;
      }
      curr = curr.parentNode;
    }
  }

  closest(selector) {
    let curr = this;
    while (curr) {
      if (curr._matchesSelector(selector)) return curr;
      curr = curr.parentNode;
    }
    return null;
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

  querySelector(selector) {
    return this.querySelectorAll(selector)[0] || null;
  }

  querySelectorAll(selector) {
    const results = [];
    const traverse = (node) => {
      for (const child of node.childNodes) {
        if (child._matchesSelector(selector)) {
          results.push(child);
        }
        traverse(child);
      }
    };
    traverse(this);
    return results;
  }
}

class MockDocument extends MockElement {
  constructor() {
    super('#document');
    this.body = new MockElement('body');
    this.body.parentNode = this;
    this.childNodes = [this.body];
  }

  createElement(tag) {
    return new MockElement(tag);
  }

  getElementById(id) {
    const traverse = (node) => {
      if (node.id === id) return node;
      for (const child of node.childNodes) {
        const found = traverse(child);
        if (found) return found;
      }
      return null;
    };
    return traverse(this);
  }
}

// ---------------------------------------------------------------------------
// 2. Setup Environment
// ---------------------------------------------------------------------------

function setupEnvironment() {
  const htmlPath = path.resolve(__dirname, '..', 'ui_improved.html');
  const htmlContent = fs.readFileSync(htmlPath, 'utf8');

  const wtStart = htmlContent.indexOf('const WidgetTemplates = {');
  const wmEnd = htmlContent.indexOf('window.widgetManager = widgetManager;', wtStart);
  if (wtStart === -1 || wmEnd === -1) {
    throw new Error('Could not locate WidgetTemplates or WidgetManager in ui_improved.html');
  }
  const genUiCode = htmlContent.slice(wtStart, wmEnd + 'window.widgetManager = widgetManager;'.length);

  const actStart = htmlContent.indexOf('function sendWidgetAction(');
  const actEnd = htmlContent.indexOf('// Start WebSocket connection on load', actStart);
  if (actStart === -1 || actEnd === -1) {
    throw new Error('Could not locate sendWidgetAction in ui_improved.html');
  }
  const actionCode = htmlContent.slice(actStart, actEnd);

  const document = new MockDocument();
  const uiLayer = document.createElement('div');
  uiLayer.className = 'ui-layer';
  document.body.appendChild(uiLayer);

  const rightHud = document.createElement('div');
  rightHud.className = 'right-hud interactive';
  uiLayer.appendChild(rightHud);

  const dock = document.createElement('div');
  dock.id = 'gen-ui-dock';
  dock.className = 'gen-ui-dock interactive';
  uiLayer.appendChild(dock);

  const chatHistory = document.createElement('div');
  chatHistory.id = 'chat-history';
  uiLayer.appendChild(chatHistory);

  const actionsSent = [];
  const mockWs = {
    readyState: 1, // OPEN
    send: (msg) => {
      actionsSent.push(JSON.parse(msg));
    }
  };

  const context = {
    console: console,
    setTimeout: setTimeout,
    clearTimeout: clearTimeout,
    document: document,
    window: {
      innerWidth: 1920,
      innerHeight: 1080,
      addEventListener: () => {}
    },
    ws: mockWs,
    WebSocket: { OPEN: 1, CLOSED: 3, CONNECTING: 0, CLOSING: 2 },
    sfx: {
      click: () => {},
      stateSwitch: () => {}
    },
    actionsSent: actionsSent
  };

  context.window.document = document;
  vm.createContext(context);

  vm.runInContext(genUiCode, context);
  vm.runInContext(actionCode, context);

  return {
    document,
    dock,
    chatHistory,
    widgetManager: context.window.widgetManager,
    WidgetTemplates: context.window.WidgetTemplates,
    sendWidgetAction: context.window.sendWidgetAction,
    actionsSent,
    context
  };
}

let passed = 0;
let failed = 0;

function assert(condition, name) {
  if (condition) {
    console.log(`  ✓ PASS: ${name}`);
    passed++;
  } else {
    console.error(`  ✗ FAIL: ${name}`);
    failed++;
    throw new Error(`Assertion failed: ${name}`);
  }
}

async function runAdversarialAudit() {
  console.log('=== RUNNING M4 PHASE 2 CHALLENGER 2 ADVERSARIAL COVERAGE AUDIT ===\n');

  // =========================================================================
  // Challenge 1: Extreme DOM Saturation Burst (1,000 Widgets)
  // =========================================================================
  console.log('[Challenge 1: Extreme DOM Saturation Burst (1,000 Rapid Renders)]');
  {
    const env = setupEnvironment();
    const wm = env.widgetManager;

    const burstCount = 1000;
    const t0 = Date.now();
    for (let i = 1; i <= burstCount; i++) {
      wm.renderWidget({
        id: `burst_${i}`,
        template: 'telemetry',
        title: `Burst Card ${i}`,
        data: { cpu: i % 100 }
      });
    }
    const elapsed = Date.now() - t0;
    console.log(`  -> 1,000 burst renders executed in ${elapsed}ms (${(burstCount / (elapsed || 1) * 1000).toFixed(0)} renders/sec)`);

    assert(wm.widgets.size === 4, 'WidgetManager registry strictly capped at 4 active entries immediately after 1,000 renders');
    const activeKeys = Array.from(wm.widgets.keys());
    assert(
      JSON.stringify(activeKeys) === JSON.stringify(['burst_997', 'burst_998', 'burst_999', 'burst_1000']),
      'Active keys in registry are strictly the newest 4 widgets'
    );

    // Evicted widgets immediately return false on update without crash
    assert(wm.updateWidget('burst_1', { cpu: 99 }) === false, 'Evicted widget burst_1 gracefully rejects updates');
    assert(wm.updateWidget('burst_500', { cpu: 50 }) === false, 'Evicted widget burst_500 gracefully rejects updates');
    assert(wm.updateWidget('burst_1000', { cpu: 88 }) === true, 'Surviving widget burst_1000 accepts updates');

    // Wait for the exit animation safety timer (450ms) to clear dismissing DOM cards
    await new Promise((resolve) => {
      setTimeout(() => {
        const domCount = env.dock.childNodes.length;
        console.log(`  -> DOM nodes in dock after transition cleanup: ${domCount}`);
        assert(domCount === 4, 'After transition window, exactly 4 DOM elements remain in dock (no DOM node leak)');
        resolve();
      }, 450);
    });

    // Test with custom maxDockWidgets = 1 (single-slot modal dock)
    const env1 = setupEnvironment();
    const WidgetManagerClass1 = env1.widgetManager.constructor;
    const wm1 = new WidgetManagerClass1({ maxDockWidgets: 1 });
    for (let i = 1; i <= 20; i++) {
      wm1.renderWidget({ id: `single_${i}`, template: 'telemetry', title: `Single ${i}` });
    }
    assert(wm1.widgets.size === 1, 'maxDockWidgets: 1 strictly maintained');
    assert(wm1.widgets.has('single_20') === true, 'Newest single_20 is the sole surviving widget');
  }

  // =========================================================================
  // Challenge 2: Deep Event Propagation & Click Delegation
  // =========================================================================
  console.log('\n[Challenge 2: Deep Event Propagation & Click Delegation]');
  {
    const env = setupEnvironment();
    const wm = env.widgetManager;

    wm.renderWidget({
      id: 'adv_controls',
      template: 'action_grid',
      title: 'Advanced Controls',
      data: {
        items: [
          { action_id: 'btn_purge', label: 'Purge Cache', icon: 'zap', payload: { all: true, tag: "sys:v1" } },
          { action_id: 'btn_toggle_proxy', label: 'Proxy Route', toggle: true, active: false }
        ]
      }
    });

    const card = env.dock.childNodes[0];

    // 2.1 Nested SVG/Icon Click Delegation
    const purgeBtn = card.querySelector('[data-action-id="btn_purge"]');
    assert(purgeBtn !== null, 'Purge button found in card');
    const iconSpan = purgeBtn.querySelector('.gen-tile-icon');
    const svgEl = iconSpan ? iconSpan.querySelector('svg') : null;
    assert(svgEl !== null, 'SVG icon nested inside button');

    // Click directly on nested SVG element
    svgEl.dispatchEvent({ type: 'click' });
    const purgeAction = env.actionsSent.find(a => a.action_id === 'btn_purge');
    assert(purgeAction !== null, 'Click on nested SVG successfully dispatched through event delegation');
    assert(purgeAction.widget_id === 'adv_controls', 'Emitted action carries correct widget_id');
    assert(purgeAction.payload.all === true, 'Parsed payload preserved from data-payload attribute');

    // 2.2 Stateful Toggle Inversion
    const toggleBtn = card.querySelector('[data-action-id="btn_toggle_proxy"]');
    assert(toggleBtn !== null, 'Toggle button found in card');
    const toggleLabel = toggleBtn.querySelector('.gen-tile-label');
    assert(toggleLabel !== null, 'Label inside toggle button');

    // First click: false -> true
    toggleLabel.dispatchEvent({ type: 'click' });
    assert(toggleBtn.classList.contains('active') === true, 'Toggle button became active on first click');
    const act1 = env.actionsSent.filter(a => a.action_id === 'btn_toggle_proxy').pop();
    assert(act1.payload.active === true, 'First toggle click sent payload { active: true }');

    // Second click: true -> false
    toggleBtn.dispatchEvent({ type: 'click' });
    assert(toggleBtn.classList.contains('active') === false, 'Toggle button deactivated on second click');
    const act2 = env.actionsSent.filter(a => a.action_id === 'btn_toggle_proxy').pop();
    assert(act2.payload.active === false, 'Second toggle click sent payload { active: false }');

    // 2.3 Close Button Dismissal & Reason
    const closeBtn = card.querySelector('.gen-ui-close-btn');
    assert(closeBtn !== null, 'Close button present');
    closeBtn.dispatchEvent({ type: 'click' });
    const closeAction = env.actionsSent.find(a => a.action_id === 'dismiss');
    assert(closeAction !== null, 'Dismiss action dispatched on close button click');
    assert(closeAction.payload.reason === 'user_close', 'Close payload carries reason: user_close');
  }

  // =========================================================================
  // Challenge 3: Template Rendering Exception Boundaries & Fallback Cards
  // =========================================================================
  console.log('\n[Challenge 3: Template Rendering Exception Boundaries]');
  {
    const env = setupEnvironment();
    const wm = env.widgetManager;

    // Register a broken template that throws an unhandled runtime error
    wm.registerTemplate('crashing_template', {
      render: () => {
        throw new Error('Uncaught rendering fault: <script>evil()</script>');
      },
      update: () => {
        throw new Error('Update fault');
      }
    });

    // Render widget with crashing template
    const entry = wm.renderWidget({
      id: 'faulty_widget',
      template: 'crashing_template',
      title: 'Fault Tolerant Test'
    });

    assert(entry !== null, 'renderWidget gracefully handled exception and returned non-null entry');
    assert(wm.widgets.has('faulty_widget') === true, 'Faulty widget successfully registered in wm.widgets');
    assert(env.dock.childNodes.length === 1, 'Error boundary card mounted in dock');

    const errorHtml = entry.containerEl.innerHTML;
    assert(errorHtml.includes('ERROR'), 'Fallback card displays ERROR badge');
    assert(!errorHtml.includes('<script>evil()'), 'Uncaught error message properly escaped without XSS injection');
    assert(errorHtml.includes('&lt;script&gt;evil()&lt;/script&gt;'), 'Error message HTML entities escaped');

    // Update with crashing updater
    const updateResult = wm.updateWidget('faulty_widget', { some: 'data' });
    assert(updateResult === true, 'updateWidget handled exception in template updater without crashing');

    // Dismissal of error card via close button
    const closeBtn = entry.containerEl.querySelector('.gen-ui-close-btn');
    assert(closeBtn !== null, 'Error card has dismiss button');
    closeBtn.dispatchEvent({ type: 'click' });
    assert(entry.containerEl.classList.contains('dismissing'), 'Error card marked with dismissing animation class');
    entry.containerEl.dispatchEvent({ type: 'transitionend' });
    assert(wm.widgets.has('faulty_widget') === false, 'Error card dismissed cleanly from registry');
  }

  // =========================================================================
  // Challenge 4: XSS & HTML Injection Sanitization Across All Templates
  // =========================================================================
  console.log('\n[Challenge 4: Multi-Template XSS & Injection Sanitization]');
  {
    const env = setupEnvironment();
    const wm = env.widgetManager;

    const xssPayloads = [
      '<script>alert("xss")</script>',
      '<img src=x onerror=alert(1)>',
      '"><svg onload=alert(1)>',
      '\' onfocus=\'alert(1)',
      'javascript:alert(1)'
    ];

    // 4.1 Telemetry Template with XSS
    const telemEntry = wm.renderWidget({
      id: 'xss_telem',
      template: 'telemetry',
      title: xssPayloads[0],
      icon: 'zap',
      data: {
        status: xssPayloads[1],
        metrics: [
          { id: xssPayloads[2], label: xssPayloads[3], value: 42, unit: xssPayloads[4] }
        ],
        gauge: { value: 75, unit: xssPayloads[0] }
      },
      actions: [
        { action_id: xssPayloads[1], label: xssPayloads[2], variant: xssPayloads[3] }
      ]
    });

    const telemHtml = telemEntry.containerEl.innerHTML;
    assert(!telemHtml.includes('<script>'), 'Telemetry template rendered zero unescaped <script> tags');
    assert(!telemHtml.includes('<img src=x'), 'Telemetry template rendered zero unescaped <img> tags');
    assert(!telemHtml.includes('<svg onload='), 'Telemetry template rendered zero unescaped <svg onload> tags');

    // 4.2 Activity Tracker Template with XSS
    const actEntry = wm.renderWidget({
      id: 'xss_act',
      template: 'activity_tracker',
      title: xssPayloads[1],
      data: {
        status: xssPayloads[0],
        detail: xssPayloads[2],
        steps: [
          { label: xssPayloads[3], completed: true },
          { name: xssPayloads[4], current: true }
        ]
      }
    });

    const actHtml = actEntry.containerEl.innerHTML;
    assert(!actHtml.includes('<script>'), 'Activity tracker rendered zero unescaped <script> tags');
    assert(!actHtml.includes('<img src=x'), 'Activity tracker rendered zero unescaped <img> tags');
    assert(!actHtml.includes('<svg onload='), 'Activity tracker rendered zero unescaped <svg onload> tags');

    // 4.3 Action Grid Template with XSS
    const gridEntry = wm.renderWidget({
      id: 'xss_grid',
      template: 'action_grid',
      title: xssPayloads[2],
      data: {
        desc: xssPayloads[0],
        items: [
          { action_id: xssPayloads[1], label: xssPayloads[3], badge: xssPayloads[4] }
        ]
      }
    });

    const gridHtml = gridEntry.containerEl.innerHTML;
    assert(!gridHtml.includes('<script>'), 'Action grid rendered zero unescaped <script> tags');
    assert(!gridHtml.includes('<img src=x'), 'Action grid rendered zero unescaped <img> tags');
    assert(!gridHtml.includes('<svg onload='), 'Action grid rendered zero unescaped <svg onload> tags');
  }

  // =========================================================================
  // Challenge 5: Malformed Data Payloads & Boundary Resilience
  // =========================================================================
  console.log('\n[Challenge 5: Malformed Data Payloads & Boundary Resilience]');
  {
    const env = setupEnvironment();
    const wm = env.widgetManager;

    // 5.1 Null, undefined, primitive data structures
    const brokenSchemas = [
      { id: 'b_null_data', template: 'telemetry', data: null },
      { id: 'b_undef_data', template: 'telemetry', data: undefined },
      { id: 'b_num_data', template: 'telemetry', data: 42 },
      { id: 'b_str_data', template: 'telemetry', data: 'malformed_string' },
      { id: 'b_null_metrics', template: 'telemetry', data: { metrics: null } },
      { id: 'b_array_nulls', template: 'telemetry', data: { metrics: [null, undefined, 123, 'str', {}] } },
      { id: 'b_gauge_null', template: 'telemetry', data: { gauge: null } },
      { id: 'b_gauge_nan', template: 'telemetry', data: { gauge: { value: 'not_a_num', max: 0 } } },
      { id: 'b_sparkline_short', template: 'telemetry', data: { sparkline: [10] } },
      { id: 'b_sparkline_nan', template: 'telemetry', data: { sparkline: [NaN, null, undefined, 'abc'] } },
      { id: 'b_steps_null', template: 'activity_tracker', data: { steps: null } },
      { id: 'b_steps_primitives', template: 'activity_tracker', data: { steps: [null, 42, 'str', true] } },
      { id: 'b_items_null', template: 'action_grid', data: { items: null } },
      { id: 'b_items_primitives', template: 'action_grid', data: { items: [null, false, 999] } },
      { id: 'b_actions_null', template: 'action_grid', actions: null },
      { id: 'b_actions_primitives', template: 'action_grid', actions: [null, 'act', 123] }
    ];

    for (const s of brokenSchemas) {
      const e = wm.renderWidget(s);
      assert(e !== null, `Schema '${s.id}' rendered successfully without crash`);
    }

    // 5.2 Malformed delta updates
    const liveWidget = wm.renderWidget({ id: 'live_test', template: 'telemetry' });
    assert(wm.updateWidget('live_test', null) === false, 'update with null delta returns false safely');
    assert(wm.updateWidget('live_test', undefined) === false, 'update with undefined delta returns false safely');
    assert(wm.updateWidget('live_test', 'string') === false, 'update with string delta returns false safely');
    assert(wm.updateWidget('live_test', 12345) === false, 'update with number delta returns false safely');
    assert(wm.updateWidget('live_test', { metrics: [null, undefined, { value: NaN }] }) === true, 'update with malformed metrics array passes safely');
    assert(wm.updateWidget('live_test', { gauge: { value: null } }) === true, 'update with null gauge value passes safely');
  }

  // =========================================================================
  // Challenge 6: WebSocket Offline & Error Handling
  // =========================================================================
  console.log('\n[Challenge 6: WebSocket Offline & Error Handling]');
  {
    const env = setupEnvironment();
    const wm = env.widgetManager;

    // 6.1 WebSocket in CLOSED state
    env.context.ws.readyState = 3; // CLOSED
    const sentWhenClosed = env.sendWidgetAction('w_offline', 'btn_test', { foo: 'bar' });
    assert(sentWhenClosed === false, 'sendWidgetAction returns false when WebSocket is CLOSED');

    // 6.2 WebSocket is null
    env.context.ws = null;
    const sentWhenNull = env.sendWidgetAction('w_offline', 'btn_test', { foo: 'bar' });
    assert(sentWhenNull === false, 'sendWidgetAction returns false when WebSocket is null');

    // 6.3 emitAction with throwing onAction handler
    let errorLogged = false;
    const WidgetManagerClass2 = env.widgetManager.constructor;
    const wmWithThrowingAction = new WidgetManagerClass2({
      onAction: () => {
        throw new Error('User handler exception');
      }
    });
    // emitAction should catch and not throw
    wmWithThrowingAction.emitAction('w_1', 'action_fail', {});
    assert(true, 'wm.emitAction safely isolated callback error without propagating exception');
  }

  console.log(`\n======================================================`);
  console.log(`ALL ADVERSARIAL TESTS COMPLETED: ${passed} passed, ${failed} failed`);
  console.log(`======================================================`);

  if (failed > 0) {
    process.exit(1);
  }
}

runAdversarialAudit().catch(err => {
  console.error('Adversarial suite crashed with unhandled error:', err);
  process.exit(1);
});
