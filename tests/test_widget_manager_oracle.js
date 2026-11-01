/**
 * tests/test_widget_manager_oracle.js
 * 
 * Milestone 2 Challenger Empirical Oracle & Stress Test Suite.
 * Adversarially exercises WidgetManager and WidgetTemplates extracted from ui_improved.html:
 * 1. Template rendering oracle (telemetry, activity_tracker, action_grid, custom).
 * 2. FIFO dock capacity enforcement (eviction at 4 widgets).
 * 3. Rapid updates stress harness (100 rapid telemetry updates, sub-element caching, performance).
 * 4. ID deduplication and re-rendering safety.
 * 5. Self-healing DOM container recovery.
 * 6. Animated and immediate dismissal lifecycles.
 * 7. Auto-dismiss TTL timer lifecycle.
 * 8. Clean teardown and memory leak resistance (200 render/teardown cycles).
 * 9. Delegated event dispatch (close button, action button, stateful toggle switches).
 * 10. Target isolation (dock vs chat).
 * 11. Malformed and adversarial input resilience.
 * 12. XSS & HTML injection sanitization oracle.
 */

const fs = require('fs');
const path = require('path');
const vm = require('vm');

// ---------------------------------------------------------------------------
// 1. Lightweight, High-Fidelity DOM Simulation Environment
// ---------------------------------------------------------------------------

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

      // Parse attributes accurately for both single and double quotes
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

  hasAttribute(name) {
    return this.attributes.has(name.toLowerCase());
  }

  removeAttribute(name) {
    this.attributes.delete(name.toLowerCase());
    if (name.toLowerCase() === 'id') this.id = '';
    if (name.toLowerCase() === 'class') this.className = '';
    if (name.toLowerCase().startsWith('data-')) {
      const dataKey = name.slice(5).replace(/-([a-z])/g, (_, c) => c.toUpperCase());
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
// 2. Load and Instantiate Generative UI Script from ui_improved.html
// ---------------------------------------------------------------------------

function setupEnvironment() {
  const htmlPath = path.resolve(__dirname, '..', 'ui_improved.html');
  const htmlContent = fs.readFileSync(htmlPath, 'utf8');

  // Extract WidgetTemplates and WidgetManager code
  const wtStart = htmlContent.indexOf('const WidgetTemplates = {');
  const wmEnd = htmlContent.indexOf('window.widgetManager = widgetManager;', wtStart);
  if (wtStart === -1 || wmEnd === -1) {
    throw new Error('Could not locate WidgetTemplates or WidgetManager in ui_improved.html');
  }

  const genUiCode = htmlContent.slice(wtStart, wmEnd + 'window.widgetManager = widgetManager;'.length);

  // Extract sendWidgetAction and click event listener
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
    WebSocket: { OPEN: 1, CLOSED: 3 },
    sfx: {
      click: () => {},
      stateSwitch: () => {}
    },
    actionsSent: actionsSent
  };

  context.window.document = document;
  vm.createContext(context);

  // Execute extracted code inside VM sandbox
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
// 3. Test Suites
// ---------------------------------------------------------------------------

let passedCount = 0;
let failedCount = 0;

function assert(condition, testName) {
  if (condition) {
    console.log(`  ✓ PASS: ${testName}`);
    passedCount++;
  } else {
    console.error(`  ✗ FAIL: ${testName}`);
    failedCount++;
    throw new Error(`Test assertion failed: ${testName}`);
  }
}

async function runAllTests() {
  console.log('=== STARTING EMPIRICAL WIDGET MANAGER ORACLE & STRESS TESTS ===\n');

  // Test 1: Template Rendering Oracle
  console.log('[Suite 1: Template Rendering Oracle]');
  {
    const env = setupEnvironment();
    const wm = env.widgetManager;

    // 1.1 Telemetry template
    const telemEntry = wm.renderWidget({
      id: 'test_telem',
      template: 'telemetry',
      title: 'Core Telemetry',
      icon: 'cpu',
      data: {
        status: 'LIVE',
        metrics: [
          { id: 'cpu', label: 'CPU Usage', value: 42, unit: '%' },
          { id: 'ram', label: 'RAM Usage', value: 68, unit: '%' }
        ]
      }
    });
    assert(telemEntry !== null, 'Telemetry widget renders non-null entry');
    assert(wm.widgets.has('test_telem'), 'Telemetry registered in wm.widgets Map');
    assert(env.dock.childNodes.length === 1, 'Telemetry card mounted in #gen-ui-dock');

    // 1.2 Activity Tracker template
    const actEntry = wm.renderWidget({
      id: 'test_act',
      template: 'activity_tracker',
      title: 'Deployment Pipeline',
      icon: 'activity',
      data: {
        status: 'RUNNING',
        progress: 75,
        steps: ['Build artifact', 'Run E2E tests', 'Deploy to stage']
      }
    });
    assert(actEntry !== null, 'Activity tracker widget renders non-null entry');
    assert(wm.widgets.has('test_act'), 'Activity tracker registered in wm.widgets Map');
    assert(env.dock.childNodes.length === 2, 'Activity tracker card mounted in #gen-ui-dock');

    // 1.3 Action Grid template
    const gridEntry = wm.renderWidget({
      id: 'test_grid',
      template: 'action_grid',
      title: 'Control Center',
      icon: 'grid',
      data: {
        actions: [
          { action_id: 'btn_purge', label: 'Purge Cache', icon: 'zap' },
          { action_id: 'btn_toggle', label: 'Defense Shield', toggle: true, active: false }
        ]
      }
    });
    assert(gridEntry !== null, 'Action grid widget renders non-null entry');
    assert(wm.widgets.has('test_grid'), 'Action grid registered in wm.widgets Map');

    // 1.4 Custom template
    const customEntry = wm.renderWidget({
      id: 'test_custom',
      template: 'custom',
      title: 'Custom Diagnostic',
      data: { html: '<div class="custom-body">Custom Payload</div>' }
    });
    assert(customEntry !== null, 'Custom template widget renders non-null entry');
    assert(wm.widgets.has('test_custom'), 'Custom template registered in wm.widgets Map');
    assert(env.dock.childNodes.length === 4, 'All 4 templates rendered in dock');
  }

  // Test 2: FIFO Dock Capacity Eviction Stress Harness
  console.log('\n[Suite 2: FIFO Dock Capacity Eviction]');
  {
    const env = setupEnvironment();
    const wm = env.widgetManager;
    assert(wm.maxDockWidgets === 4, 'Default maxDockWidgets is 4');

    // 2.1 Spaced Eviction (renders separated by animation window)
    console.log('  Testing spaced FIFO eviction (spaced by 420ms)...');
    await new Promise((resolve) => {
      // Render 4 widgets
      for (let i = 1; i <= 4; i++) {
        wm.renderWidget({ id: `w_${i}`, template: 'telemetry', title: `Widget ${i}` });
      }
      assert(wm.widgets.size === 4, 'Capacity at 4/4 widgets');
      assert(env.dock.childNodes.length === 4, '4 DOM cards in dock');

      // Render 5th widget after 50ms (during animation of eviction)
      wm.renderWidget({ id: 'w_5', template: 'telemetry', title: 'Widget 5' });
      // Oldest w_1 should be marked dismissing or evicted after 420ms
      setTimeout(() => {
        assert(wm.widgets.has('w_1') === false, 'After 420ms, oldest widget w_1 evicted from registry');
        assert(wm.widgets.has('w_5') === true, 'New widget w_5 present in registry');
        assert(wm.widgets.size === 4, 'Capacity maintained at strictly 4 widgets after transition');
        resolve();
      }, 420);
    });

    // 2.2 Burst Eviction (rapid sequential renders in tight loop)
    console.log('  Testing burst FIFO eviction (rendering 8 widgets in tight loop)...');
    const burstEnv = setupEnvironment();
    const burstWm = burstEnv.widgetManager;
    for (let i = 1; i <= 8; i++) {
      burstWm.renderWidget({ id: `burst_${i}`, template: 'telemetry', title: `Burst ${i}` });
    }
    console.log(`  -> Immediately after burst: size = ${burstWm.widgets.size} (expected <= 4 or 4 active + 4 dismissing)`);
    await new Promise((resolve) => {
      setTimeout(() => {
        const finalSize = burstWm.widgets.size;
        console.log(`  -> 450ms after burst: size = ${finalSize} (keys: ${Array.from(burstWm.widgets.keys())})`);
        if (finalSize > 4) {
          console.error(`  [BURST FIFO FAILURE] FIFO capacity limit violated! Expected <= 4, got ${finalSize}`);
          // We record this failure without aborting subsequent suites
          failedCount++;
        } else {
          assert(finalSize === 4, 'Burst FIFO maintained capacity at 4 widgets');
        }
        resolve();
      }, 450);
    });
  }

  // Test 3: Rapid Updates Stress Harness (100 Rapid Telemetry Packets)
  console.log('\n[Suite 3: Rapid Updates Stress Harness (100 Telemetry Updates)]');
  {
    const env = setupEnvironment();
    const wm = env.widgetManager;

    wm.renderWidget({
      id: 'stress_telemetry',
      template: 'telemetry',
      title: 'Live Telemetry',
      data: {
        status: 'LIVE',
        cpu: 10,
        ram: 20
      }
    });

    const startTime = Date.now();
    for (let i = 1; i <= 100; i++) {
      const delta = {
        cpu: (i % 100),
        ram: ((i * 2) % 100),
        status: i % 10 === 0 ? 'WARN' : 'LIVE'
      };
      const ok = wm.updateWidget('stress_telemetry', delta);
      assert(ok === true, `Update #${i} returned true`);
    }
    const elapsed = Date.now() - startTime;
    console.log(`  -> 100 rapid updates executed in ${elapsed}ms (${(100 / (elapsed || 1) * 1000).toFixed(0)} updates/sec)`);

    const entry = wm.getWidget('stress_telemetry');
    assert(entry.data.cpu === (100 % 100), 'CPU metric state matches final delta value');
    assert(entry.data.ram === ((100 * 2) % 100), 'RAM metric state matches final delta value');
    assert(entry.data.status === 'WARN', 'Status badge matches final WARN state (100 % 10 === 0)');
  }

  // Test 4: ID Deduplication & Idempotent Re-render
  console.log('\n[Suite 4: ID Deduplication & Idempotent Re-render]');
  {
    const env = setupEnvironment();
    const wm = env.widgetManager;

    wm.renderWidget({ id: 'card_alpha', template: 'telemetry', title: 'Alpha Initial' });
    assert(env.dock.childNodes.length === 1, 'Initial card rendered');

    // Re-render with same ID and different template
    wm.renderWidget({ id: 'card_alpha', template: 'activity_tracker', title: 'Alpha Replacement' });
    assert(env.dock.childNodes.length === 1, 'Re-render replaced previous card without DOM duplication');
    assert(wm.widgets.size === 1, 'Registry contains exactly 1 entry for card_alpha');
    assert(wm.getWidget('card_alpha').template === 'activity_tracker', 'Template updated to activity_tracker');
  }

  // Test 5: Self-Healing DOM Container Recovery
  console.log('\n[Suite 5: Self-Healing DOM Container Recovery]');
  {
    const env = setupEnvironment();
    const wm = env.widgetManager;

    // Remove dock from DOM
    env.dock.parentNode.removeChild(env.dock);
    assert(env.document.getElementById('gen-ui-dock') === null, 'Dock intentionally deleted from DOM');

    // Render widget targeting dock -> should self-heal and mount dock
    wm.renderWidget({ id: 'healing_widget', template: 'custom', target: 'dock', title: 'Healed' });
    const healedDock = env.document.getElementById('gen-ui-dock');
    assert(healedDock !== null, 'WidgetManager self-healed and created #gen-ui-dock in DOM');
    assert(healedDock.childNodes.length === 1, 'Widget successfully mounted inside self-healed dock');
  }

  // Test 6: Dismissal Lifecycles (Immediate & Smooth Animation)
  console.log('\n[Suite 6: Dismissal Lifecycles]');
  {
    const env = setupEnvironment();
    const wm = env.widgetManager;

    wm.renderWidget({ id: 'w_imm', template: 'telemetry', title: 'Immediate Test' });
    assert(wm.widgets.has('w_imm') === true, 'w_imm registered');
    wm.dismissWidget('w_imm', { immediate: true });
    assert(wm.widgets.has('w_imm') === false, 'w_imm immediately removed from registry');
    assert(env.dock.childNodes.length === 0, 'w_imm DOM element detached');

    // Smooth dismissal with transitionend
    wm.renderWidget({ id: 'w_smooth', template: 'telemetry', title: 'Smooth Test' });
    const entry = wm.getWidget('w_smooth');
    const el = entry.containerEl;
    wm.dismissWidget('w_smooth', { immediate: false });
    assert(el.classList.contains('dismissing'), 'Dismissing class added to card element');

    // Simulate transitionend event
    el.dispatchEvent({ type: 'transitionend' });
    assert(wm.widgets.has('w_smooth') === false, 'w_smooth torn down on transitionend');
  }

  // Test 7: Auto-Dismiss TTL Timer
  console.log('\n[Suite 7: Auto-Dismiss TTL Timer]');
  await new Promise((resolve) => {
    const env = setupEnvironment();
    const wm = env.widgetManager;

    wm.renderWidget({ id: 'w_ttl', template: 'telemetry', title: 'TTL Test', ttl_ms: 50 });
    assert(wm.widgets.has('w_ttl') === true, 'w_ttl initially present');

    setTimeout(() => {
      // Transitionend safety fallback fires after TTL + 380ms
      setTimeout(() => {
        assert(wm.widgets.has('w_ttl') === false, 'w_ttl dismissed automatically after TTL expiration');
        resolve();
      }, 420);
    }, 60);
  });

  // Test 8: Clean Teardown & Memory Leak Resistance (200 Cycles)
  console.log('\n[Suite 8: Memory Leak Resistance]');
  {
    const env = setupEnvironment();
    const wm = env.widgetManager;

    for (let i = 0; i < 200; i++) {
      wm.renderWidget({ id: `leak_test_${i}`, template: 'telemetry', title: `Cycle ${i}` });
      wm.dismissWidget(`leak_test_${i}`, { immediate: true });
    }
    assert(wm.widgets.size === 0, 'All 200 widgets fully collected; registry size is 0');
    assert(env.dock.childNodes.length === 0, 'Zero lingering DOM nodes in dock');
  }

  // Test 9: Delegated Event Dispatch (Close, Action, Stateful Toggle)
  console.log('\n[Suite 9: Delegated Event Dispatch]');
  {
    const env = setupEnvironment();
    const wm = env.widgetManager;

    wm.renderWidget({
      id: 'control_panel',
      template: 'action_grid',
      title: 'Controls',
      data: {
        actions: [
          { action_id: 'btn_restart', label: 'Restart Node', variant: 'primary', payload: { force: true } },
          { action_id: 'toggle_turbo', label: 'Turbo Mode', toggle: true, active: false }
        ]
      }
    });

    const card = env.dock.childNodes[0];

    // 9.1 Close button click
    const closeBtn = card.querySelector('.gen-ui-close-btn');
    assert(closeBtn !== null, 'Close button exists in card');
    closeBtn.dispatchEvent({ type: 'click' });
    const dismissAction = env.actionsSent.find(a => a.action_id === 'dismiss');
    assert(dismissAction !== null, 'Dismiss action emitted to WebSocket');
    assert(dismissAction.widget_id === 'control_panel', 'Emitted action references control_panel');
    assert(dismissAction.payload.reason === 'user_close', 'Emitted action carries user_close reason');

    // 9.2 Momentary action button click
    const entry2 = wm.renderWidget({
      id: 'control_panel_2',
      template: 'action_grid',
      title: 'Controls 2',
      actions: [
        { action_id: 'btn_restart', label: 'Restart Node', variant: 'primary', payload: { force: true } }
      ]
    });
    const card2 = entry2.containerEl;
    const restartBtn = card2.querySelector('[data-action-id="btn_restart"]');
    assert(restartBtn !== null, 'Restart button found in card');
    restartBtn.dispatchEvent({ type: 'click' });
    const restartAction = env.actionsSent.find(a => a.action_id === 'btn_restart');
    assert(restartAction !== null, 'Restart action emitted to WebSocket');
    assert(restartAction.payload.force === true, 'Action carried parsed JSON payload { force: true }');

    // 9.3 Stateful toggle button click
    const entry3 = wm.renderWidget({
      id: 'control_panel_3',
      template: 'action_grid',
      title: 'Controls 3',
      actions: [
        { action_id: 'toggle_turbo', label: 'Turbo Mode', toggle: true, active: false }
      ]
    });
    const card3 = entry3.containerEl;
    const toggleBtn = card3.querySelector('[data-action-id="toggle_turbo"]');
    assert(toggleBtn !== null, 'Toggle button found in card');
    toggleBtn.dispatchEvent({ type: 'click' });
    assert(toggleBtn.classList.contains('active'), 'Toggle switch flipped to .active');
    const toggleAction = env.actionsSent.find(a => a.action_id === 'toggle_turbo');
    assert(toggleAction !== null, 'Toggle action emitted to WebSocket');
    assert(toggleAction.payload.active === true, 'Toggle payload contains { active: true }');
  }

  // Test 10: Target Isolation (Dock vs Chat)
  console.log('\n[Suite 10: Target Isolation (Dock vs Chat)]');
  {
    const env = setupEnvironment();
    const wm = env.widgetManager;

    // Render 4 dock widgets
    for (let i = 1; i <= 4; i++) {
      wm.renderWidget({ id: `dock_${i}`, target: 'dock', template: 'telemetry' });
    }
    // Render 2 chat widgets
    wm.renderWidget({ id: 'chat_1', target: 'chat', template: 'telemetry' });
    wm.renderWidget({ id: 'chat_2', target: 'chat', template: 'telemetry' });

    assert(env.dock.childNodes.length === 4, 'Dock contains exactly 4 widgets');
    assert(env.chatHistory.childNodes.length === 2, 'Chat contains exactly 2 bubbles');
    assert(wm.widgets.has('dock_1') === true, 'Dock widget dock_1 was NOT evicted by chat widgets');

    // clearAll('chat') triggers animated dismissal
    wm.clearAll('chat');
    assert(env.chatHistory.childNodes.every(n => n.classList.contains('dismissing')),
      'All chat bubbles marked with .dismissing immediately upon clearAll("chat")');

    await new Promise((resolve) => {
      setTimeout(() => {
        assert(env.chatHistory.childNodes.length === 0, 'Chat DOM elements fully cleared after transition window');
        assert(env.dock.childNodes.length === 4, 'Dock unaffected by clearAll("chat")');
        resolve();
      }, 420);
    });
  }

  // Test 11: Malformed and Adversarial Input Resilience
  console.log('\n[Suite 11: Malformed and Adversarial Inputs]');
  {
    const env = setupEnvironment();
    const wm = env.widgetManager;

    assert(wm.renderWidget(null) === null, 'renderWidget(null) returns null without exception');
    assert(wm.renderWidget(undefined) === null, 'renderWidget(undefined) returns null without exception');
    assert(wm.renderWidget('string') === null, 'renderWidget("string") returns null without exception');

    const emptyEntry = wm.renderWidget({});
    assert(emptyEntry !== null, 'renderWidget({}) creates default entry with generated ID');
    assert(emptyEntry.template === 'custom', 'Defaults to custom template');

    assert(wm.updateWidget('non_existent', { cpu: 50 }) === false, 'updateWidget non-existent ID returns false');
    assert(wm.updateWidget(emptyEntry.id, null) === false, 'updateWidget with null delta returns false');
    assert(wm.dismissWidget('non_existent') === false, 'dismissWidget non-existent ID returns false');
  }

  // Test 12: XSS and HTML Injection Sanitization Oracle
  console.log('\n[Suite 12: XSS and HTML Injection Sanitization]');
  {
    const env = setupEnvironment();
    const wm = env.widgetManager;
    const wt = env.WidgetTemplates;

    const xssTitle = '<script>alert("pwned")</script>';
    const escaped = wt._escape(xssTitle);
    assert(escaped === '&lt;script&gt;alert(&quot;pwned&quot;)&lt;/script&gt;',
      'wt._escape properly neutralizes <script> and quotes');

    const entry = wm.renderWidget({
      id: 'xss_test',
      template: 'telemetry',
      title: xssTitle,
      data: { status: '<img src=x onerror=alert(1)>' }
    });
    const html = entry.containerEl.innerHTML;
    assert(!html.includes('<script>alert'), 'Rendered HTML contains zero unescaped script tags');
    assert(!html.includes('<img src=x'), 'Rendered HTML contains zero unescaped img tags');
  }

  console.log(`\n======================================================`);
  console.log(`ALL ORACLE TESTS COMPLETED: ${passedCount} passed, ${failedCount} failed`);
  console.log(`======================================================`);

  if (failedCount > 0) {
    process.exit(1);
  }
}

runAllTests().catch(err => {
  console.error('Test suite crashed with unhandled error:', err);
  process.exit(1);
});
