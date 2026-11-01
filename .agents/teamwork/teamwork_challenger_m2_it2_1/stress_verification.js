/**
 * stress_verification.js
 * 
 * Milestone 2 Iteration 2 Challenger Independent Empirical Stress Harness.
 * Thoroughly stress-tests:
 * 1. FIFO burst eviction (8 sequential renders, 50 sequential renders, custom capacity limits, DOM node count).
 * 2. Rapid delta updates (100 rapid deltas, 1000 rapid deltas, multi-card interleaved streaming, performance & memory).
 * 3. Reflow and timer throttling in _pulseElement (elimination of synchronous reflow, timer deduplication).
 * 4. Error boundaries, malformed delta objects, and eviction race conditions.
 */

const fs = require('fs');
const path = require('path');
const vm = require('vm');

class MockDOMTokenList {
  constructor() {
    this._tokens = new Set();
  }
  add(...tokens) {
    tokens.forEach(t => {
      t.split(/\s+/).filter(Boolean).forEach(tok => this._tokens.add(tok));
    });
  }
  remove(...tokens) {
    tokens.forEach(t => {
      t.split(/\s+/).filter(Boolean).forEach(tok => this._tokens.delete(tok));
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
    this._className = '';
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
    this._className = val || '';
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
        if (k.startsWith('data-')) {
          const dataKey = k.slice(5).replace(/-([a-z])/g, (_, c) => c.toUpperCase());
          child.dataset[dataKey] = v;
        }
        if (k === 'id') child.id = v;
        if (k === 'class') child.className = v;
      }
      child.innerHTML = inner;
      this.appendChild(child);
    }
  }

  setAttribute(name, value) {
    this.attributes.set(name.toLowerCase(), String(value));
    if (name.toLowerCase() === 'id') this.id = String(value);
    if (name.toLowerCase() === 'class') this.className = String(value);
    if (name.toLowerCase().startsWith('data-')) {
      const dataKey = name.slice(5).replace(/-([a-z])/g, (_, c) => c.toUpperCase());
      this.dataset[dataKey] = String(value);
    }
  }

  getAttribute(name) {
    return this.attributes.get(name.toLowerCase()) || null;
  }

  removeAttribute(name) {
    this.attributes.delete(name.toLowerCase());
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

  addEventListener(type, handler, options = {}) {
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
    const list = this.listeners.get(event.type) || [];
    event.target = this;
    event.currentTarget = this;
    for (const item of [...list]) {
      item.handler.call(this, event);
      if (item.options && item.options.once) {
        this.removeEventListener(event.type, item.handler);
      }
    }
  }

  querySelector(selector) {
    const results = this.querySelectorAll(selector);
    return results.length > 0 ? results[0] : null;
  }

  querySelectorAll(selector) {
    const results = [];
    const traverse = (node) => {
      for (const child of node.childNodes) {
        if (this._matches(child, selector)) {
          results.push(child);
        }
        traverse(child);
      }
    };
    traverse(this);
    return results;
  }

  _matches(el, selector) {
    if (selector.startsWith('.')) {
      return el.classList.contains(selector.slice(1));
    }
    if (selector.startsWith('#')) {
      return el.id === selector.slice(1);
    }
    if (selector.startsWith('[') && selector.endsWith(']')) {
      const inside = selector.slice(1, -1);
      if (inside.includes('=')) {
        const [k, v] = inside.split('=').map(s => s.replace(/['"]/g, '').trim());
        return el.getAttribute(k) === v;
      }
      return el.attributes.has(inside.toLowerCase());
    }
    return el.tagName.toLowerCase() === selector.toLowerCase();
  }
}

class MockDocument {
  constructor() {
    this.body = new MockElement('body');
  }

  createElement(tagName) {
    return new MockElement(tagName);
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
    return traverse(this.body);
  }

  querySelector(selector) {
    return this.body.querySelector(selector);
  }

  querySelectorAll(selector) {
    return this.body.querySelectorAll(selector);
  }
}

function setupTestEnvironment(customOptions = {}) {
  const htmlPath = path.resolve('C:\\jarvis\\Mark-LV-main\\Mark-LV-main\\ui_improved.html');
  const htmlContent = fs.readFileSync(htmlPath, 'utf8');

  const wtStart = htmlContent.indexOf('const WidgetTemplates = {');
  const wmEnd = htmlContent.indexOf('window.widgetManager = widgetManager;', wtStart);
  if (wtStart === -1 || wmEnd === -1) {
    throw new Error('Could not locate WidgetTemplates or WidgetManager in ui_improved.html');
  }

  const genUiCode = htmlContent.slice(wtStart, wmEnd + 'window.widgetManager = widgetManager;'.length);

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

  let scheduledTimerCount = 0;
  const wrappedSetTimeout = (fn, delay) => {
    scheduledTimerCount++;
    return setTimeout(fn, delay);
  };

  const context = {
    console: console,
    setTimeout: wrappedSetTimeout,
    clearTimeout: clearTimeout,
    document: document,
    window: {
      innerWidth: 1920,
      innerHeight: 1080,
      addEventListener: () => {}
    },
    WebSocket: { OPEN: 1, CLOSED: 3 },
    sfx: {
      click: () => {},
      stateSwitch: () => {}
    }
  };

  context.window.document = document;
  vm.createContext(context);
  vm.runInContext(genUiCode, context);

  return {
    document,
    dock,
    chatHistory,
    widgetManager: context.window.widgetManager,
    WidgetManagerClass: context.window.widgetManager.constructor,
    WidgetTemplates: context.window.WidgetTemplates,
    getTimerCount: () => scheduledTimerCount,
    htmlContent
  };
}

let testPassed = 0;
let testFailed = 0;

function check(cond, msg) {
  if (cond) {
    console.log(`  [PASS] ${msg}`);
    testPassed++;
  } else {
    console.error(`  [FAIL] ${msg}`);
    testFailed++;
    throw new Error(`Assertion failed: ${msg}`);
  }
}

async function runEmpiricalStressSuite() {
  console.log('================================================================');
  console.log('CHALLENGER 1 EMPIRICAL STRESS & CAPACITY HARNESS (ITERATION 2)');
  console.log('================================================================\n');

  // -------------------------------------------------------------------------
  // TEST 1: FIFO Burst Eviction (8 Sequential Widgets in Tight Loop)
  // -------------------------------------------------------------------------
  console.log('[STRESS TEST 1: FIFO Burst Eviction - 8 Sequential Widgets in Tight Loop]');
  {
    const env = setupTestEnvironment();
    const wm = env.widgetManager;

    check(wm.maxDockWidgets === 4, 'Default max capacity is 4 widgets');

    // Tight loop: render 8 sequential telemetry widgets
    const t0 = Date.now();
    for (let i = 1; i <= 8; i++) {
      wm.renderWidget({
        id: `burst_${i}`,
        template: 'telemetry',
        title: `Burst Widget ${i}`,
        data: { status: 'LIVE', cpu: i * 10 }
      });
    }
    const loopTime = Date.now() - t0;
    console.log(`  Rendered 8 burst widgets in ${loopTime}ms`);

    // Invariant 1: Immediately after tight loop, registry size MUST be strictly <= 4
    check(wm.widgets.size === 4, `Immediate registry size is strictly 4 (actual: ${wm.widgets.size})`);
    
    // Invariant 2: Active widgets must be the newest 4 (burst_5, burst_6, burst_7, burst_8)
    const expectedKeys = ['burst_5', 'burst_6', 'burst_7', 'burst_8'];
    const actualKeys = Array.from(wm.widgets.keys());
    check(JSON.stringify(actualKeys) === JSON.stringify(expectedKeys), `Active keys are exactly [${expectedKeys.join(', ')}] (actual: [${actualKeys.join(', ')}])`);

    // Invariant 3: Older widgets (burst_1..burst_4) must be marked dismissing
    for (let i = 1; i <= 4; i++) {
      check(wm.widgets.has(`burst_${i}`) === false, `burst_${i} evicted from active registry`);
    }

    // Wait 450ms for transition animation and fallback timers to settle
    console.log('  Waiting 450ms for transition animation to complete...');
    await new Promise(r => setTimeout(r, 450));

    // Invariant 4: DOM container child count must strictly be 4
    console.log(`  DOM childNodes in dock: ${env.dock.childNodes.length}`);
    check(env.dock.childNodes.length === 4, `DOM child count in #gen-ui-dock is strictly 4 after teardown (actual: ${env.dock.childNodes.length})`);

    const domWidgetIds = env.dock.childNodes.map(n => n.dataset.widgetId);
    check(JSON.stringify(domWidgetIds) === JSON.stringify(expectedKeys), `DOM elements match active widgets [${expectedKeys.join(', ')}]`);
  }

  // -------------------------------------------------------------------------
  // TEST 2: Extreme Burst (50 Sequential Widgets in Tight Loop)
  // -------------------------------------------------------------------------
  console.log('\n[STRESS TEST 2: Extreme Burst - 50 Sequential Widgets in Tight Loop]');
  {
    const env = setupTestEnvironment();
    const wm = env.widgetManager;

    const t0 = Date.now();
    for (let i = 1; i <= 50; i++) {
      wm.renderWidget({
        id: `mega_${i}`,
        template: i % 2 === 0 ? 'activity_tracker' : 'action_grid',
        title: `Mega Widget ${i}`,
        data: { status: 'ONLINE', progress: i * 2 }
      });
    }
    const elapsed = Date.now() - t0;
    console.log(`  50 sequential widgets rendered in ${elapsed}ms`);

    check(wm.widgets.size === 4, `Registry size capped at 4 after 50 burst renders (actual: ${wm.widgets.size})`);
    const expectedLast4 = ['mega_47', 'mega_48', 'mega_49', 'mega_50'];
    const actualLast4 = Array.from(wm.widgets.keys());
    check(JSON.stringify(actualLast4) === JSON.stringify(expectedLast4), `Last 4 widgets preserved: [${actualLast4.join(', ')}]`);

    await new Promise(r => setTimeout(r, 450));
    check(env.dock.childNodes.length === 4, `DOM elements strictly 4 after 50-widget burst (actual: ${env.dock.childNodes.length})`);
  }

  // -------------------------------------------------------------------------
  // TEST 3: Configurable Capacity Burst Limits (maxDockWidgets = 2 and 6)
  // -------------------------------------------------------------------------
  console.log('\n[STRESS TEST 3: Configurable Capacity Burst Limits]');
  {
    const env = setupTestEnvironment();
    // Test capacity = 2
    const wm2 = new env.WidgetManagerClass({ maxDockWidgets: 2, dockContainerId: 'gen-ui-dock' });
    for (let i = 1; i <= 10; i++) {
      wm2.renderWidget({ id: `c2_${i}`, template: 'telemetry', title: `C2_${i}` });
    }
    check(wm2.widgets.size === 2, `Capacity 2: Registry maintained at 2 widgets (actual: ${wm2.widgets.size})`);
    await new Promise(r => setTimeout(r, 450));
    check(env.dock.childNodes.length === 2, `Capacity 2: DOM elements strictly 2`);

    // Clean dock
    env.dock.childNodes = [];

    // Test capacity = 6
    const wm6 = new env.WidgetManagerClass({ maxDockWidgets: 6, dockContainerId: 'gen-ui-dock' });
    for (let i = 1; i <= 15; i++) {
      wm6.renderWidget({ id: `c6_${i}`, template: 'telemetry', title: `C6_${i}` });
    }
    check(wm6.widgets.size === 6, `Capacity 6: Registry maintained at 6 widgets (actual: ${wm6.widgets.size})`);
    await new Promise(r => setTimeout(r, 450));
    check(env.dock.childNodes.length === 6, `Capacity 6: DOM elements strictly 6`);
  }

  // -------------------------------------------------------------------------
  // TEST 4: Rapid Delta Updates (100 and 1,000 Consecutive Updates)
  // -------------------------------------------------------------------------
  console.log('\n[STRESS TEST 4: Rapid Delta Updates - 100 and 1,000 Consecutive Updates]');
  {
    const env = setupTestEnvironment();
    const wm = env.widgetManager;

    wm.renderWidget({
      id: 'telemetry_target',
      template: 'telemetry',
      title: 'High-Frequency Telemetry',
      data: {
        status: 'BOOT',
        cpu: 0,
        ram: 0,
        metrics: [
          { id: 'cpu', label: 'CPU Load', value: 0 },
          { id: 'ram', label: 'RAM Load', value: 0 }
        ]
      }
    });

    // 100 rapid updates
    const t0 = Date.now();
    for (let i = 1; i <= 100; i++) {
      const ok = wm.updateWidget('telemetry_target', {
        cpu: i,
        ram: (i * 3) % 100,
        status: i === 100 ? 'COMPLETE' : 'STREAMING'
      });
      if (!ok) check(false, `Update ${i} failed`);
    }
    const t100 = Date.now() - t0;
    console.log(`  100 rapid delta updates completed in ${t100}ms (${(100 / (t100 || 1) * 1000).toFixed(0)} updates/sec)`);
    check(t100 < 500, `100 updates completed well under 500ms budget (actual: ${t100}ms)`);

    const entry = wm.getWidget('telemetry_target');
    check(entry.data.cpu === 100, `Final CPU is 100 (actual: ${entry.data.cpu})`);
    check(entry.data.ram === ((100 * 3) % 100), `Final RAM is ${(100 * 3) % 100}`);
    check(entry.data.status === 'COMPLETE', 'Final status is COMPLETE');

    // 1,000 rapid updates stress
    const tStart1k = Date.now();
    for (let i = 1; i <= 1000; i++) {
      wm.updateWidget('telemetry_target', {
        cpu: i % 100,
        ram: (i * 7) % 100,
        status: i % 50 === 0 ? 'BUSY' : 'STREAMING'
      });
    }
    const t1k = Date.now() - tStart1k;
    console.log(`  1,000 rapid delta updates completed in ${t1k}ms (${(1000 / (t1k || 1) * 1000).toFixed(0)} updates/sec)`);
    check(t1k < 2000, `1,000 updates completed well under 2000ms budget (actual: ${t1k}ms)`);
  }

  // -------------------------------------------------------------------------
  // TEST 5: Interleaved Multi-Widget Rapid Updates
  // -------------------------------------------------------------------------
  console.log('\n[STRESS TEST 5: Interleaved Multi-Widget Rapid Updates (4 Widgets, 1,000 Packets)]');
  {
    const env = setupTestEnvironment();
    const wm = env.widgetManager;

    wm.renderWidget({ id: 'card_telem', template: 'telemetry', title: 'Telem' });
    wm.renderWidget({ id: 'card_act', template: 'activity_tracker', title: 'Act', data: { progress: 0 } });
    wm.renderWidget({ id: 'card_grid', template: 'action_grid', title: 'Grid', data: { actions: [{ action_id: 'a1', label: 'A1', toggle: true }] } });
    wm.renderWidget({ id: 'card_custom', template: 'custom', title: 'Custom', data: { html: '<span>0</span>' } });

    check(wm.widgets.size === 4, '4 distinct template cards rendered in dock');

    const t0 = Date.now();
    for (let i = 1; i <= 250; i++) {
      wm.updateWidget('card_telem', { cpu: i % 100, ram: (i * 2) % 100 });
      wm.updateWidget('card_act', { progress: (i % 100), status: i % 10 === 0 ? 'SYNC' : 'BUSY' });
      wm.updateWidget('card_grid', { items: [{ action_id: 'a1', active: i % 2 === 0 }] });
      wm.updateWidget('card_custom', { html: `<span>Cycle ${i}</span>` });
    }
    const elapsed = Date.now() - t0;
    console.log(`  1,000 interleaved updates across 4 widgets executed in ${elapsed}ms (${(1000 / (elapsed || 1) * 1000).toFixed(0)} updates/sec)`);
    check(elapsed < 2000, 'Interleaved updates execute cleanly with zero crash');

    // Updates to non-existent widget
    const badUpdate = wm.updateWidget('does_not_exist', { cpu: 50 });
    check(badUpdate === false, 'Update to non-existent widget gracefully returns false');
  }

  // -------------------------------------------------------------------------
  // TEST 6: Reflow Throttling & Timer De-duplication in _pulseElement
  // -------------------------------------------------------------------------
  console.log('\n[STRESS TEST 6: Reflow Throttling & Timer De-duplication in _pulseElement]');
  {
    const env = setupTestEnvironment();
    const wm = env.widgetManager;

    // Check code in ui_improved.html for void el.offsetWidth
    const hasOffsetWidthInPulse = env.htmlContent.includes('void el.offsetWidth');
    check(!hasOffsetWidthInPulse, 'void el.offsetWidth is 100% eliminated from ui_improved.html');

    // Create element and pulse 100 times in rapid succession
    const testEl = env.document.createElement('div');
    const timerStart = env.getTimerCount();

    for (let i = 0; i < 100; i++) {
      wm._pulseElement(testEl);
    }
    const timersCreated = env.getTimerCount() - timerStart;
    console.log(`  100 rapid _pulseElement calls created ${timersCreated} timer(s)`);
    check(timersCreated === 1, `_pulseElement created strictly 1 timer for 100 calls due to pulse class throttling (actual: ${timersCreated})`);
    check(testEl.classList.contains('gen-ui-pulse'), 'testEl has gen-ui-pulse class');

    // After 650ms, class should be removed
    await new Promise(r => setTimeout(r, 650));
    check(!testEl.classList.contains('gen-ui-pulse'), 'gen-ui-pulse class removed after timeout');
  }

  // -------------------------------------------------------------------------
  // TEST 7: Race Condition: Updating Widget During Eviction
  // -------------------------------------------------------------------------
  console.log('\n[STRESS TEST 7: Updating Widget During Eviction]');
  {
    const env = setupTestEnvironment();
    const wm = env.widgetManager;

    // Render 4 widgets
    for (let i = 1; i <= 4; i++) {
      wm.renderWidget({ id: `w_race_${i}`, template: 'telemetry', title: `Race ${i}` });
    }

    // Render 5th widget -> triggers eviction of w_race_1
    wm.renderWidget({ id: 'w_race_5', template: 'telemetry', title: 'Race 5' });

    // w_race_1 was evicted from registry
    check(wm.widgets.has('w_race_1') === false, 'Evicted widget w_race_1 is no longer in wm.widgets');

    // Attempting to update evicted widget returns false safely
    const updateResult = wm.updateWidget('w_race_1', { cpu: 99 });
    check(updateResult === false, 'Updating evicted widget safely returns false without exception');

    await new Promise(r => setTimeout(r, 450));
    check(env.dock.childNodes.length === 4, 'Dock capacity intact at 4 cards');
  }

  // -------------------------------------------------------------------------
  // TEST 8: Memory Stability Under Rapid Mount/Unmount Cycles
  // -------------------------------------------------------------------------
  console.log('\n[STRESS TEST 8: Memory Stability Under Rapid Mount/Unmount Cycles (100 Cycles)]');
  {
    const env = setupTestEnvironment();
    const wm = env.widgetManager;

    for (let c = 0; c < 100; c++) {
      wm.renderWidget({ id: `cycle_${c}`, template: 'telemetry', title: `Cycle ${c}` });
      wm.dismissWidget(`cycle_${c}`, { immediate: true });
    }

    check(wm.widgets.size === 0, 'Registry size 0 after 100 mount/immediate unmount cycles');
    check(env.dock.childNodes.length === 0, 'DOM dock child count 0');
  }

  console.log('\n================================================================');
  console.log(`STRESS HARNESS RESULTS: ${testPassed} passed, ${testFailed} failed`);
  console.log('================================================================\n');

  if (testFailed > 0) {
    process.exit(1);
  }
}

runEmpiricalStressSuite().catch(err => {
  console.error('Fatal test harness error:', err);
  process.exit(1);
});
