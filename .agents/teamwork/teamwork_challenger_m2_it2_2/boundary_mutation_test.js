/**
 * boundary_mutation_test.js
 * 
 * Milestone 2 Iteration 2 Challenger 2: Adversarial Boundary, Mutation & Negative Testing.
 * Tests:
 * 1. Sparse array handling in templates and delta updaters:
 *    - telemetry (metrics: [null], [undefined], holes, primitives, empty objects)
 *    - activity_tracker (steps: [null], [undefined], holes, primitives, empty objects)
 *    - action_grid (items: [null], [undefined], holes, primitives, empty objects)
 *    - renderActions (actions: [null], cyclic payload, holes)
 *    - updateTelemetry, updateActivityTracker, updateActionGrid with sparse/corrupt arrays
 * 2. Template exception handling in _generateHtml:
 *    - Broken custom template throwing Error
 *    - Broken custom template throwing primitive string / null / object
 *    - Broken built-in template throwing Error
 *    - XSS injection in error card title and error message
 *    - Clean dismissal of fallback error card
 * 3. clearAll(target, options) with immediate and animated dismissal:
 *    - Immediate vs animated dismissal
 *    - Target filtering (dock vs chat vs nonexistent)
 *    - Argument normalization (options as 1st argument)
 *    - WebSocket inbound widget_clear_all handler routing
 * 4. Mutation, burst FIFO capacity and rapid state stress:
 *    - 50-widget rapid burst FIFO enforcement
 *    - Dismissal idempotency under duplicate calls
 *    - Rapid render / clear interleaving (100 cycles)
 *    - Type mutations on schema attributes
 */

const fs = require('fs');
const path = require('path');
const vm = require('vm');

// ---------------------------------------------------------------------------
// 1. DOM Mock Engine
// ---------------------------------------------------------------------------

class MockDOMTokenList {
  constructor() {
    this._tokens = new Set();
  }
  add(...tokens) {
    tokens.forEach(t => {
      if (!t) return;
      String(t).split(/\s+/).filter(Boolean).forEach(tok => this._tokens.add(tok));
    });
  }
  remove(...tokens) {
    tokens.forEach(t => {
      if (!t) return;
      String(t).split(/\s+/).filter(Boolean).forEach(tok => this._tokens.delete(tok));
    });
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
    this._parseSimpleHTML(this._innerHTML);
  }

  _parseSimpleHTML(html) {
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
  const htmlPath = path.resolve(__dirname, '..', '..', '..', 'ui_improved.html');
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
    throw new Error('Could not locate sendWidgetAction or delegated click listener in ui_improved.html');
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
    readyState: 1,
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
    WebSocket: { OPEN: 1, CLOSED: 3 },
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

// ---------------------------------------------------------------------------
// 3. Test Runner & Assertion Harness
// ---------------------------------------------------------------------------

let passed = 0;
let failed = 0;

function assert(condition, message) {
  if (!condition) {
    console.error(`  ✗ FAIL: ${message}`);
    failed++;
    throw new Error(`Assertion failed: ${message}`);
  } else {
    console.log(`  ✓ PASS: ${message}`);
    passed++;
  }
}

async function runAdversarialBoundaryTests() {
  console.log('=== RUNNING CHALLENGER 2: BOUNDARY, MUTATION & NEGATIVE TESTS ===\n');

  // =========================================================================
  // SUITE 1: SPARSE & CORRUPT ARRAY HANDLING IN TEMPLATES AND UPDATERS
  // =========================================================================
  console.log('[Suite 1: Sparse & Malformed Array Handling]');
  {
    const env = setupEnvironment();
    const wt = env.WidgetTemplates;
    const wm = env.widgetManager;

    // 1.1 telemetry with sparse arrays
    console.log('  -> Testing telemetry sparse array permutations...');
    const sparseTelemetryPermutations = [
      { id: 't_null', data: { metrics: [null] } },
      { id: 't_undef', data: { metrics: [undefined] } },
      { id: 't_mixed', data: { metrics: [null, undefined, { id: 'cpu', label: 'CPU', value: 45, unit: '%' }, null] } },
      { id: 't_primitives', data: { metrics: [123, 'plain-string', true, false] } },
      { id: 't_empty_obj', data: { metrics: [{}] } },
      { id: 't_null_props', data: { metrics: [{ id: null, label: null, value: null, unit: null }] } },
      { id: 't_nan_inf', data: { metrics: [{ id: 'nan', value: NaN }, { id: 'inf', value: Infinity }, { id: 'zero_max', value: 10, max: 0 }] } },
      { id: 't_empty_arr', data: { metrics: [] } },
      { id: 't_not_arr', data: { metrics: 'not_an_array' } },
      { id: 't_null_metrics', data: { metrics: null } },
      { id: 't_sparkline_sparse', data: { sparkline: [null, undefined, 10, 'bad', NaN, 20] } },
      { id: 't_sparkline_empty', data: { sparkline: [] } },
      { id: 't_gauge_null', data: { gauge: null } },
      { id: 't_gauge_null_val', data: { gauge: { value: null, max: null } } },
      { id: 't_gauge_str', data: { gauge: 'invalid_object' } }
    ];

    // Sparse array with holes: new Array(5)
    const holeArray = new Array(5);
    holeArray[2] = { id: 'hole_metric', value: 75 };
    sparseTelemetryPermutations.push({ id: 't_holes', data: { metrics: holeArray } });

    for (const perm of sparseTelemetryPermutations) {
      let html = '';
      try {
        html = wt.telemetry(perm);
      } catch (err) {
        assert(false, `wt.telemetry threw exception on ${perm.id}: ${err.message}`);
      }
      assert(typeof html === 'string' && html.length > 0, `wt.telemetry gracefully rendered ${perm.id}`);
    }

    // 1.2 activity_tracker with sparse arrays
    console.log('  -> Testing activity_tracker sparse array permutations...');
    const sparseTrackerPermutations = [
      { id: 'a_null', data: { steps: [null] } },
      { id: 'a_undef', data: { steps: [undefined] } },
      { id: 'a_mixed', data: { steps: [null, { label: 'Step 1', completed: true }, undefined, { name: 'Step 2', current: true }, null] } },
      { id: 'a_primitives', data: { steps: [42, 'raw_string', false, true] } },
      { id: 'a_empty_obj', data: { steps: [{}] } },
      { id: 'a_null_props', data: { steps: [{ label: null, name: null, completed: null, current: null }] } },
      { id: 'a_empty_arr', data: { steps: [] } },
      { id: 'a_not_arr', data: { steps: 'not_array' } },
      { id: 'a_null_steps', data: { steps: null } },
      { id: 'a_nan_progress', data: { progress: NaN, status: null } },
      { id: 'a_neg_progress', data: { progress: -100 } },
      { id: 'a_huge_progress', data: { progress: 9999 } }
    ];

    const holeSteps = new Array(4);
    holeSteps[1] = { label: 'Middle Step', completed: true };
    sparseTrackerPermutations.push({ id: 'a_holes', data: { steps: holeSteps } });

    for (const perm of sparseTrackerPermutations) {
      let html = '';
      try {
        html = wt.activity_tracker(perm);
      } catch (err) {
        assert(false, `wt.activity_tracker threw exception on ${perm.id}: ${err.message}`);
      }
      assert(typeof html === 'string' && html.length > 0, `wt.activity_tracker gracefully rendered ${perm.id}`);
    }

    // 1.3 action_grid with sparse arrays
    console.log('  -> Testing action_grid sparse array permutations...');
    const sparseGridPermutations = [
      { id: 'g_null_items', data: { items: [null] } },
      { id: 'g_undef_items', data: { items: [undefined] } },
      { id: 'g_mixed_items', data: { items: [null, { action_id: 'btn1', label: 'B1' }, undefined, null] } },
      { id: 'g_null_buttons', data: { buttons: [null] } },
      { id: 'g_primitives', data: { items: [123, 'action', false] } },
      { id: 'g_empty_obj', data: { items: [{}] } },
      { id: 'g_null_props', data: { items: [{ action_id: null, label: null, toggle: null, active: null, payload: null }] } },
      { id: 'g_empty_arr', data: { items: [] } },
      { id: 'g_not_arr', data: { items: 'bad' } },
      { id: 'g_null_data', data: { items: null, buttons: null } }
    ];

    const holeItems = new Array(3);
    holeItems[0] = { action_id: 'hole_btn', label: 'Hole' };
    sparseGridPermutations.push({ id: 'g_holes', data: { items: holeItems } });

    for (const perm of sparseGridPermutations) {
      let html = '';
      try {
        html = wt.action_grid(perm);
      } catch (err) {
        assert(false, `wt.action_grid threw exception on ${perm.id}: ${err.message}`);
      }
      assert(typeof html === 'string' && html.length > 0, `wt.action_grid gracefully rendered ${perm.id}`);
    }

    // 1.4 renderActions with sparse arrays & circular payloads
    console.log('  -> Testing renderActions sparse array & payload permutations...');
    const circularPayload = { a: 1 };
    circularPayload.self = circularPayload; // circular reference

    const sparseActionPermutations = [
      [null],
      [undefined],
      [null, { action_id: 'save', label: 'Save' }, undefined, null],
      [999, 'bad_action', true],
      [{}],
      [{ action_id: null, label: null, variant: null, payload: null }],
      [{ action_id: 'circular', label: 'Circ', payload: circularPayload }],
      [],
      null,
      undefined,
      'not_an_array'
    ];

    for (let i = 0; i < sparseActionPermutations.length; i++) {
      let html = '';
      try {
        html = wt.renderActions('widget_actions_test', sparseActionPermutations[i]);
      } catch (err) {
        assert(false, `wt.renderActions threw exception on perm ${i}: ${err.message}`);
      }
      assert(typeof html === 'string', `wt.renderActions returned valid string on perm ${i}`);
    }

    // 1.5 Delta Updaters with sparse / malformed data
    console.log('  -> Testing delta updaters on mounted cards with sparse deltas...');
    const teleEntry = wm.renderWidget({
      id: 'tele_live',
      template: 'telemetry',
      data: { metrics: [{ id: 'cpu', label: 'CPU', value: 10 }] }
    });

    try {
      wt.updateTelemetry(teleEntry.containerEl, { metrics: [null] });
      wt.updateTelemetry(teleEntry.containerEl, { metrics: [undefined] });
      wt.updateTelemetry(teleEntry.containerEl, { metrics: [null, { id: 'cpu', value: 85 }] });
      wt.updateTelemetry(teleEntry.containerEl, { gauge: null });
      wt.updateTelemetry(teleEntry.containerEl, { gauge: { value: null } });
      wt.updateTelemetry(teleEntry.containerEl, null);
      wt.updateTelemetry(null, { metrics: [] });
      assert(true, 'updateTelemetry safely processed all sparse delta variations');
    } catch (e) {
      assert(false, `updateTelemetry threw error: ${e.message}`);
    }

    const trackerEntry = wm.renderWidget({
      id: 'track_live',
      template: 'activity_tracker',
      data: { steps: [{ label: 'Init', completed: false }] }
    });

    try {
      wt.updateActivityTracker(trackerEntry.containerEl, { progress: null });
      wt.updateActivityTracker(trackerEntry.containerEl, { progress: 'invalid' });
      wt.updateActivityTracker(trackerEntry.containerEl, { status: null });
      wt.updateActivityTracker(trackerEntry.containerEl, { status: 'STATUS<injection>"' });
      wt.updateActivityTracker(trackerEntry.containerEl, { detail: null, step: null });
      wt.updateActivityTracker(trackerEntry.containerEl, null);
      wt.updateActivityTracker(null, {});
      assert(true, 'updateActivityTracker safely processed all sparse delta variations');
    } catch (e) {
      assert(false, `updateActivityTracker threw error: ${e.message}`);
    }

    const gridEntry = wm.renderWidget({
      id: 'grid_live',
      template: 'action_grid',
      data: { items: [{ action_id: 'btn1', label: 'Btn 1' }] }
    });

    try {
      wt.updateActionGrid(gridEntry.containerEl, { items: [null] });
      wt.updateActionGrid(gridEntry.containerEl, { items: [undefined, { action_id: 'btn1', active: true, badge: 'ACTIVE' }, null] });
      wt.updateActionGrid(gridEntry.containerEl, { buttons: [null] });
      wt.updateActionGrid(gridEntry.containerEl, null);
      wt.updateActionGrid(null, {});
      assert(true, 'updateActionGrid safely processed all sparse delta variations');
    } catch (e) {
      assert(false, `updateActionGrid threw error: ${e.message}`);
    }
  }

  // =========================================================================
  // SUITE 2: TEMPLATE EXCEPTION HANDLING IN _generateHtml & FALLBACK CARD
  // =========================================================================
  console.log('\n[Suite 2: Template Exception Handling in _generateHtml]');
  {
    const env = setupEnvironment();
    const wm = env.widgetManager;
    const wt = env.WidgetTemplates;

    // 2.1 Broken registered custom template throwing standard Error
    wm.registerTemplate('crashing_template', {
      render: () => {
        throw new Error('Simulated crash inside template engine');
      }
    });

    const crashEntry1 = wm.renderWidget({
      id: 'crash_w1',
      template: 'crashing_template',
      title: 'Crash Test 1'
    });

    assert(crashEntry1 !== null, 'renderWidget returned valid entry despite template throw');
    assert(wm.widgets.has('crash_w1'), 'Entry registered in wm.widgets map');
    const html1 = crashEntry1.containerEl.innerHTML;
    assert(html1.includes('gen-ui-header'), 'Fallback card rendered gen-ui-header');
    assert(html1.includes('gen-ui-badge danger'), 'Fallback card contains danger badge');
    assert(html1.includes('ERROR'), 'Fallback card displays ERROR badge text');
    assert(html1.includes('data-widget-dismiss') || html1.includes('gen-ui-close-btn'), 'Fallback card contains dismiss button');
    assert(html1.includes('Simulated crash inside template engine'), 'Fallback card contains escaped error message');

    // 2.2 Broken template throwing a primitive string
    wm.registerTemplate('string_throw_template', {
      render: () => {
        throw 'Primitive string error thrown';
      }
    });

    const crashEntry2 = wm.renderWidget({
      id: 'crash_w2',
      template: 'string_throw_template',
      title: 'Crash Test 2'
    });
    assert(crashEntry2 !== null, 'renderWidget returned entry when template throws primitive string');
    assert(crashEntry2.containerEl.innerHTML.includes('ERROR'), 'Fallback card renders ERROR on primitive string throw');

    // 2.3 Broken template throwing null
    wm.registerTemplate('null_throw_template', {
      render: () => {
        throw null;
      }
    });

    const crashEntry3 = wm.renderWidget({
      id: 'crash_w3',
      template: 'null_throw_template',
      title: 'Crash Test 3'
    });
    assert(crashEntry3 !== null, 'renderWidget returned entry when template throws null');
    assert(crashEntry3.containerEl.innerHTML.includes('Render Error'), 'Fallback card displays default Render Error message');

    // 2.4 Built-in template temporarily monkeypatched to throw
    const originalTelemetry = wt.telemetry;
    wt.telemetry = () => {
      throw new Error('Kernel Telemetry Failure');
    };

    const crashEntry4 = wm.renderWidget({
      id: 'crash_w4',
      template: 'telemetry',
      title: 'Builtin Telemetry'
    });
    assert(crashEntry4 !== null, 'renderWidget returned entry when built-in template throws');
    assert(crashEntry4.containerEl.innerHTML.includes('Kernel Telemetry Failure'), 'Fallback card contains builtin template error message');
    wt.telemetry = originalTelemetry; // restore

    // 2.5 Malicious payload in title and error message (XSS prevention in error card)
    wm.registerTemplate('xss_crash_template', {
      render: () => {
        throw new Error('Exploit <img src=x onerror=alert("xss_err")>');
      }
    });

    const xssEntry = wm.renderWidget({
      id: 'xss_crash',
      template: 'xss_crash_template',
      title: 'Title <script>alert("xss_title")</script>'
    });
    const xssHtml = xssEntry.containerEl.innerHTML;
    assert(!xssHtml.includes('<script>'), 'Fallback card escaped malicious title tag');
    assert(!xssHtml.includes('<img src=x'), 'Fallback card escaped malicious error message tag');
    assert(xssHtml.includes('&lt;script&gt;'), 'Fallback card contains HTML entity &lt;script&gt;');

    // 2.6 Dismissal of fallback error card
    assert(wm.widgets.has('xss_crash'), 'xss_crash is currently active in registry');
    const dismissed = wm.dismissWidget('xss_crash', { immediate: true });
    assert(dismissed === true, 'Fallback error card dismissed cleanly with immediate: true');
    assert(!wm.widgets.has('xss_crash'), 'Fallback error card removed from registry');
    assert(xssEntry.containerEl === null, 'Fallback error card element nullified for garbage collection');
  }

  // =========================================================================
  // SUITE 3: clearAll(target, options) LIFECYCLE & ARGUMENT NORMALIZATION
  // =========================================================================
  console.log('\n[Suite 3: clearAll(target, options) Lifecycles]');
  {
    const env = setupEnvironment();
    const wm = env.widgetManager;

    // 3.1 Immediate Clear All
    console.log('  -> Testing clearAll(null, { immediate: true })...');
    wm.renderWidget({ id: 'dock_1', target: 'dock', template: 'telemetry' });
    wm.renderWidget({ id: 'dock_2', target: 'dock', template: 'telemetry' });
    wm.renderWidget({ id: 'chat_1', target: 'chat', template: 'telemetry' });
    wm.renderWidget({ id: 'chat_2', target: 'chat', template: 'telemetry' });

    assert(wm.widgets.size === 4, '4 widgets registered before clearAll');
    assert(env.dock.childNodes.length === 2, '2 widgets mounted in dock');
    assert(env.chatHistory.childNodes.length === 2, '2 widgets mounted in chat');

    const clearedCount1 = wm.clearAll(null, { immediate: true });
    assert(clearedCount1 === 4, 'clearAll returned count 4');
    assert(wm.widgets.size === 0, 'wm.widgets synchronously emptied');
    assert(env.dock.childNodes.length === 0, 'Dock DOM synchronously emptied');
    assert(env.chatHistory.childNodes.length === 0, 'Chat DOM synchronously emptied');

    // 3.2 Animated Clear All
    console.log('  -> Testing clearAll(null, { immediate: false })...');
    const wD1 = wm.renderWidget({ id: 'dock_anim1', target: 'dock', template: 'telemetry' });
    const wC1 = wm.renderWidget({ id: 'chat_anim1', target: 'chat', template: 'telemetry' });

    const clearedCount2 = wm.clearAll(null, { immediate: false });
    assert(clearedCount2 === 2, 'clearAll returned count 2');
    assert(wD1.dismissing === true, 'dock widget marked dismissing');
    assert(wC1.dismissing === true, 'chat widget marked dismissing');
    assert(wD1.containerEl.classList.contains('dismissing'), 'dock card has dismissing CSS class');
    assert(wC1.containerEl.classList.contains('dismissing'), 'chat card has dismissing CSS class');

    // Wait for safety timeout to complete teardown
    await new Promise(r => setTimeout(r, 420));
    assert(wm.widgets.size === 0, 'Registry clean after animated clear completion');
    assert(env.dock.childNodes.length === 0, 'Dock DOM clean after animated clear completion');
    assert(env.chatHistory.childNodes.length === 0, 'Chat DOM clean after animated clear completion');

    // 3.3 Target Filtering: dock vs chat
    console.log('  -> Testing target-isolated clearAll("dock", { immediate: true })...');
    wm.renderWidget({ id: 'dock_t1', target: 'dock', template: 'telemetry' });
    wm.renderWidget({ id: 'dock_t2', target: 'dock', template: 'telemetry' });
    wm.renderWidget({ id: 'chat_t1', target: 'chat', template: 'telemetry' });

    const clearedDock = wm.clearAll('dock', { immediate: true });
    assert(clearedDock === 2, 'Cleared exactly 2 dock widgets');
    assert(wm.widgets.size === 1, 'Chat widget retained in registry');
    assert(wm.widgets.has('chat_t1'), 'chat_t1 is the retained widget');
    assert(env.dock.childNodes.length === 0, 'Dock DOM is empty');
    assert(env.chatHistory.childNodes.length === 1, 'Chat DOM still contains chat_t1');

    wm.clearAll('chat', { immediate: true });
    assert(wm.widgets.size === 0, 'All widgets cleared after clearing chat');

    // 3.4 Argument Signature Normalization
    console.log('  -> Testing argument signature normalization...');
    wm.renderWidget({ id: 'dock_norm1', target: 'dock', template: 'telemetry' });
    wm.renderWidget({ id: 'chat_norm1', target: 'chat', template: 'telemetry' });

    // Passing options as 1st argument: clearAll({ target: 'dock', immediate: true })
    const clearedObj = wm.clearAll({ target: 'dock', immediate: true });
    assert(clearedObj === 1, 'clearAll with options object as 1st param cleared target');
    assert(wm.widgets.has('chat_norm1'), 'Chat widget unaffected');

    // Non-existent target: returns 0 without error
    const clearedNonexistent = wm.clearAll('nonexistent_target');
    assert(clearedNonexistent === 0, 'clearAll on nonexistent target returns 0');
    assert(wm.widgets.size === 1, 'Existing widgets unaffected by nonexistent target');

    // Default clearAll() with no arguments
    const clearedDefault = wm.clearAll();
    assert(clearedDefault === 1, 'Default clearAll() cleared remaining widget');
    await new Promise(r => setTimeout(r, 420));
    assert(wm.widgets.size === 0, 'Registry empty after default clearAll completes');
  }

  // =========================================================================
  // SUITE 4: MUTATION, BURST CAPACITY & HIGH-CONCURRENCY STRESS HARNESS
  // =========================================================================
  console.log('\n[Suite 4: Mutation, Burst Capacity & High-Concurrency Stress]');
  {
    const env = setupEnvironment();
    const wm = env.widgetManager;

    // 4.1 Massive Burst (50 sequential dock widgets in tight loop)
    console.log('  -> Testing 50-widget burst FIFO capacity eviction...');
    for (let i = 0; i < 50; i++) {
      wm.renderWidget({
        id: `burst_card_${i}`,
        target: 'dock',
        template: 'telemetry',
        title: `Burst ${i}`,
        data: { metrics: [{ id: 'val', value: i }] }
      });
      // At EVERY single addition, dock capacity limit must hold
      assert(wm.widgets.size <= 4, `Step ${i}: wm.widgets.size (${wm.widgets.size}) <= 4`);
    }

    // Wait for all 46 earlier widgets to finish CSS transition
    await new Promise(r => setTimeout(r, 450));
    assert(wm.widgets.size === 4, `wm.widgets.size after burst transitions is exactly 4`);
    assert(env.dock.childNodes.length === 4, `Dock DOM nodes after burst transitions is exactly 4`);

    // Verify the 4 surviving widgets are the last 4 (46, 47, 48, 49)
    const survivingKeys = Array.from(wm.widgets.keys());
    assert(survivingKeys.join(',') === 'burst_card_46,burst_card_47,burst_card_48,burst_card_49',
      'The 4 surviving widgets are strictly the newest 4 additions');

    // 4.2 Dismiss Idempotency Under Rapid Duplicate Calls
    console.log('  -> Testing dismissal idempotency...');
    const testId = 'burst_card_49';
    // 5 consecutive animated calls
    for (let j = 0; j < 5; j++) {
      const res = wm.dismissWidget(testId, { immediate: false });
      assert(res === true, `Duplicate dismissWidget call #${j} returned true`);
    }
    // Immediate call on already dismissing widget
    const immRes = wm.dismissWidget(testId, { immediate: true });
    assert(immRes === true, 'Immediate dismiss call on dismissing widget handled cleanly');
    assert(!wm.widgets.has(testId), 'Widget immediately unregistered');

    // Calling dismiss on non-existent widget
    assert(wm.dismissWidget('already_gone_id') === false, 'dismissWidget on missing ID returns false');

    // 4.3 Rapid Interleaved Render & ClearAll Cycles (100 cycles)
    console.log('  -> Testing 100 rapid render/clear cycles...');
    for (let k = 0; k < 100; k++) {
      wm.renderWidget({ id: `cycle_${k}`, target: 'dock', template: 'telemetry' });
      wm.clearAll(null, { immediate: true });
      assert(wm.widgets.size === 0, `Cycle ${k}: size is 0 after immediate clear`);
      assert(env.dock.childNodes.length === 0, `Cycle ${k}: dock DOM is empty`);
    }

    // 4.4 Schema Type Mutation Resilience
    console.log('  -> Testing extreme schema type mutations...');
    const weirdSchemas = [
      { id: 99999, template: null, title: false, icon: 1234, target: null, data: null, actions: null },
      { id: '', template: undefined, title: null, icon: null, target: 'chat', data: 'string_data', actions: 'string_actions' },
      { id: 'symbols', template: 'custom', title: 'Special: <>&"\'', data: { html: '<b>bold</b>' }, actions: [] }
    ];

    for (const ws of weirdSchemas) {
      let entry = null;
      try {
        entry = wm.renderWidget(ws);
      } catch (err) {
        assert(false, `renderWidget crashed on weird schema: ${err.message}`);
      }
      assert(entry !== null, `renderWidget safely handled weird schema with id '${ws.id}'`);
    }

    // Clean up
    wm.clearAll(null, { immediate: true });
    assert(wm.widgets.size === 0, 'Cleaned up all mutation test widgets');
  }

  console.log('\n======================================================');
  console.log(`ALL BOUNDARY & MUTATION TESTS COMPLETED: ${passed} passed, ${failed} failed`);
  console.log('======================================================\n');

  if (failed > 0) {
    process.exit(1);
  }
}

runAdversarialBoundaryTests().catch(err => {
  console.error('Test harness exception:', err);
  process.exit(1);
});
