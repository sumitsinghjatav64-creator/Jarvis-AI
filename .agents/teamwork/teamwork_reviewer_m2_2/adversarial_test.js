// Adversarial Stress & Verification Test for Milestone 2 Generative UI in ui_improved.html
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert');

console.log('=== [ADVERSARIAL VERIFICATION & STRESS TEST: MILESTONE 2] ===\n');

const htmlPath = path.resolve('C:/jarvis/Mark-LV-main/Mark-LV-main/ui_improved.html');
const html = fs.readFileSync(htmlPath, 'utf8');

// 1. Static Layout & CSS Checks
console.log('--- 1. STATIC LAYOUT & CSS INTEGRITY ---');
assert(html.includes('id="gen-ui-dock"'), 'Missing #gen-ui-dock container in DOM');
assert(html.includes('class="gen-ui-dock interactive"'), 'Missing interactive class on #gen-ui-dock');
assert(html.includes('id="webgl-canvas"'), 'Missing #webgl-canvas in DOM');
assert(!html.includes('backdrop-filter: blur'), 'CRITICAL: backdrop-filter: blur detected in CSS (performance hazard)');
console.log('✓ Pass: Dock container present, #webgl-canvas present, backdrop-filter: blur absent.\n');

// 2. Extract and Sandbox JavaScript Engine
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
    this.tag = tag;
    this.classList = {
      _classes: new Set(),
      add(c) { this._classes.add(c); },
      remove(c) { this._classes.delete(c); },
      contains(c) { return this._classes.has(c); }
    };
    this.parentNode = { removeChild: () => {} };
    this.children = [];
    this.dataset = {};
  }
  appendChild(c) { this.children.push(c); return c; }
  querySelector() { return null; }
  querySelectorAll() { return []; }
  addEventListener() {}
  removeEventListener() {}
}

const mockDoc = {
  createElement: (t) => new MockElement(t),
  getElementById: (id) => new MockElement(id),
  querySelector: () => new MockElement('div')
};

const sandbox = {
  window: {},
  document: mockDoc,
  console: console,
  setTimeout: (fn) => 1,
  clearTimeout: () => {},
  Date: Date,
  Math: Math,
  Map: Map,
  Set: Set,
  Array: Array,
  Object: Object,
  String: String,
  Number: Number
};
sandbox.window = sandbox;
vm.createContext(sandbox);
vm.runInContext(jsCode, sandbox);

const WidgetTemplates = sandbox.WidgetTemplates;
const widgetManager = sandbox.window.widgetManager;

// 3. PoC Demonstrating DOM Injection Risks
console.log('--- 2. DOM INJECTION FINDINGS (PoC) ---');
const pocBreakout = 'metric"><img src=x onerror=alert(1)>';
const telemetryHtml = WidgetTemplates.telemetry({
  id: 'test_poc',
  template: 'telemetry',
  title: 'Safe Title',
  data: {
    metrics: [{ label: pocBreakout, value: 42, unit: '%' }]
  }
});

const isVulnerableMetricId = telemetryHtml.includes('<img src=x onerror=alert(1)>');
console.log(`PoC Metric ID Breakout injected raw <img> tag: ${isVulnerableMetricId ? 'VULNERABLE (PASSES PoC)' : 'SAFE'}`);

const gaugeValPoc = '<img src=x onerror=alert(2)>';
const gaugeHtml = WidgetTemplates.telemetry({
  id: 'test_gauge',
  template: 'telemetry',
  data: { gauge: { value: gaugeValPoc } }
});
const isVulnerableGauge = gaugeHtml.includes('<img src=x onerror=alert(2)>');
console.log(`PoC Gauge Value injected raw <img> tag: ${isVulnerableGauge ? 'VULNERABLE (PASSES PoC)' : 'SAFE'}`);

const actionVariantPoc = 'primary" onfocus="alert(3)';
const actionHtml = WidgetTemplates.telemetry({
  id: 'test_act',
  template: 'telemetry',
  actions: [{ id: 'b1', label: 'Click', variant: actionVariantPoc }]
});
const isVulnerableVariant = actionHtml.includes('class="gen-ui-btn primary" onfocus="alert(3)"');
console.log(`PoC Action Variant injected raw attribute: ${isVulnerableVariant ? 'VULNERABLE (PASSES PoC)' : 'SAFE'}`);

// 4. Burst Capacity Evaluation
console.log('\n--- 3. FIFO CAPACITY LIMIT UNDER BURST EVALUATION ---');
widgetManager.clearAll();
for (let i = 1; i <= 8; i++) {
  widgetManager.renderWidget({
    id: `burst_card_${i}`,
    template: 'telemetry',
    target: 'dock',
    data: {}
  });
}
console.log(`Dock widgets in registry after 8 burst additions: ${widgetManager.widgets.size}`);
console.log(`Expected max capacity: ${widgetManager.maxDockWidgets}`);
const isBurstOverCapacity = widgetManager.widgets.size > widgetManager.maxDockWidgets;
console.log(`Burst capacity limit breached: ${isBurstOverCapacity ? 'YES (CONFIRMED FINDING)' : 'NO'}`);

console.log('\n=== ADVERSARIAL VERIFICATION COMPLETE ===');
