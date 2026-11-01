// Deep hardening verification of WidgetManager replacement features
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const htmlPath = path.resolve('C:/jarvis/Mark-LV-main/Mark-LV-main/ui_improved.html');
let htmlContent = fs.readFileSync(htmlPath, 'utf8').replace(/\r\n/g, '\n');

// 1. renderWidget FIFO burst eviction fix
const originalRenderChunk = `        // 2. Enforce FIFO capacity limit on right dock
        if (target === 'dock') {
          const dockEntries = Array.from(this.widgets.values()).filter(e => e.target === 'dock');
          if (dockEntries.length >= this.maxDockWidgets) {
            const oldest = dockEntries[0];
            this.dismissWidget(oldest.id, { immediate: false });
          }
        }`;

const proposedRenderChunk = `        // 2. Enforce FIFO capacity limit on right dock (excluding entries already dismissing)
        if (target === 'dock') {
          const activeDockEntries = Array.from(this.widgets.values()).filter(
            e => e.target === 'dock' && !e.dismissing && (!e.containerEl || !e.containerEl.classList.contains('dismissing'))
          );
          const excessCount = (activeDockEntries.length - this.maxDockWidgets) + 1;
          for (let i = 0; i < excessCount; i++) {
            if (activeDockEntries[i]) {
              this.dismissWidget(activeDockEntries[i].id, { immediate: false });
            }
          }
        }`;

// 2. dismissWidget dismissing flag fix
const originalDismissChunk = `      dismissWidget(widgetId, options = {}) {
        const entry = this.widgets.get(widgetId);
        if (!entry) return false;

        // Clear auto-dismiss timer if active
        if (entry.dismissTimer) {
          clearTimeout(entry.dismissTimer);
          entry.dismissTimer = null;
        }

        if (options.immediate) {
          this._teardownEntry(entry);
          return true;
        }

        // Smooth exit animation
        if (typeof sfx !== 'undefined' && sfx.click) {
          sfx.click();
        }

        const el = entry.containerEl;
        if (el) {
          el.classList.add('dismissing');`;

const proposedDismissChunk = `      dismissWidget(widgetId, options = {}) {
        const entry = this.widgets.get(widgetId);
        if (!entry) return false;

        // Clear auto-dismiss timer if active
        if (entry.dismissTimer) {
          clearTimeout(entry.dismissTimer);
          entry.dismissTimer = null;
        }

        if (options && options.immediate) {
          this._teardownEntry(entry);
          return true;
        }

        // Avoid re-triggering animated dismissal if already dismissing
        if (entry.dismissing) {
          return true;
        }
        entry.dismissing = true;

        // Smooth exit animation
        if (typeof sfx !== 'undefined' && sfx.click) {
          sfx.click();
        }

        const el = entry.containerEl;
        if (el) {
          el.classList.add('dismissing');`;

// 3. clearAll options fix
const originalClearAllChunk = `      clearAll(target = null) {
        let count = 0;
        const entries = Array.from(this.widgets.values());
        for (const entry of entries) {
          if (target === null || entry.target === target) {
            this.dismissWidget(entry.id, { immediate: false });
            count++;
          }
        }
        return count;
      }`;

const proposedClearAllChunk = `      clearAll(target = null, options = {}) {
        if (target && typeof target === 'object' && !Array.isArray(target)) {
          options = target;
          target = options.target || null;
        }
        const opts = Object.assign({ immediate: false }, options);
        let count = 0;
        const entries = Array.from(this.widgets.values());
        for (const entry of entries) {
          if (target === null || entry.target === target) {
            this.dismissWidget(entry.id, opts);
            count++;
          }
        }
        return count;
      }`;

// 4. _pulseElement reflow throttling fix
const originalPulseChunk = `      _pulseElement(el) {
        if (!el) return;
        el.classList.remove('gen-ui-pulse');
        void el.offsetWidth; // Force reflow
        el.classList.add('gen-ui-pulse');
        setTimeout(() => { if (el) el.classList.remove('gen-ui-pulse'); }, 600);
      }`;

const proposedPulseChunk = `      _pulseElement(el) {
        if (!el || !el.classList) return;
        // Throttle reflow: if already pulsing, let ongoing CSS animation complete
        if (el.classList.contains('gen-ui-pulse')) return;
        el.classList.add('gen-ui-pulse');
        setTimeout(() => {
          if (el && el.classList) {
            el.classList.remove('gen-ui-pulse');
          }
        }, 600);
      }`;

// 5. WebSocket message handler widget_clear_all fix
const originalWsClearAll = `          else if (msg.type === 'widget_clear_all') {
            if (window.widgetManager) {
              window.widgetManager.clearAll(msg.target);
            }
          }`;

const proposedWsClearAll = `          else if (msg.type === 'widget_clear_all') {
            if (window.widgetManager) {
              window.widgetManager.clearAll(msg.target, msg.options || (msg.immediate !== undefined ? { immediate: Boolean(msg.immediate) } : {}));
            }
          }`;

htmlContent = htmlContent.replace(originalRenderChunk, proposedRenderChunk)
                         .replace(originalDismissChunk, proposedDismissChunk)
                         .replace(originalClearAllChunk, proposedClearAllChunk)
                         .replace(originalPulseChunk, proposedPulseChunk)
                         .replace(originalWsClearAll, proposedWsClearAll);

// Load mock environment from oracle test
const oraclePath = path.resolve('C:/jarvis/Mark-LV-main/Mark-LV-main/tests/test_widget_manager_oracle.js');
let oracleCode = fs.readFileSync(oraclePath, 'utf8').replace(
  "const htmlContent = fs.readFileSync(htmlPath, 'utf8');",
  "const htmlContent = patchedHtml;"
);

// We run test suites, plus deep hardening checks
const sandbox = {
  require: require,
  __dirname: path.dirname(oraclePath),
  console: console,
  setTimeout: setTimeout,
  clearTimeout: clearTimeout,
  process: process,
  patchedHtml: htmlContent
};

const script = new vm.Script(oracleCode);
const context = vm.createContext(sandbox);
script.runInContext(context);

// Now execute additional deep tests in the same sandbox
async function runDeepHardening() {
  console.log('\n[Suite 13: Deep Hardening for clearAll options, arbitrary bursts, and pulse throttling]');
  const env = context.setupEnvironment();
  const wm = env.widgetManager;

  // 13.1 clearAll with immediate: true (target = 'dock')
  for (let i = 1; i <= 4; i++) {
    wm.renderWidget({ id: `d_${i}`, target: 'dock', template: 'telemetry' });
  }
  for (let i = 1; i <= 2; i++) {
    wm.renderWidget({ id: `c_${i}`, target: 'chat', template: 'telemetry' });
  }
  console.log(`  Initial count: dock=${env.dock.childNodes.length}, chat=${env.chatHistory.childNodes.length}`);
  
  const clearedDock = wm.clearAll('dock', { immediate: true });
  console.log(`  wm.clearAll('dock', { immediate: true }) cleared count: ${clearedDock}`);
  if (clearedDock !== 4) throw new Error(`Expected 4 dock widgets cleared, got ${clearedDock}`);
  if (env.dock.childNodes.length !== 0) throw new Error(`Expected dock DOM children 0, got ${env.dock.childNodes.length}`);
  if (env.chatHistory.childNodes.length !== 2) throw new Error(`Chat widgets should remain untouched, got ${env.chatHistory.childNodes.length}`);

  // 13.2 clearAll with options object as first argument: clearAll({ immediate: true })
  const clearedChat = wm.clearAll({ immediate: true });
  console.log(`  wm.clearAll({ immediate: true }) cleared remaining count: ${clearedChat}`);
  if (clearedChat !== 2) throw new Error(`Expected 2 chat widgets cleared, got ${clearedChat}`);
  if (env.chatHistory.childNodes.length !== 0) throw new Error(`Expected chat DOM children 0, got ${env.chatHistory.childNodes.length}`);
  if (wm.widgets.size !== 0) throw new Error(`Registry size should be 0, got ${wm.widgets.size}`);

  // 13.3 Arbitrary burst with custom maxDockWidgets: 2 and 10 burst renders
  const wmSmall = new (wm.constructor)({ maxDockWidgets: 2, dockContainerId: 'gen-ui-dock' });
  for (let i = 1; i <= 10; i++) {
    wmSmall.renderWidget({ id: `fast_${i}`, target: 'dock', template: 'telemetry' });
  }
  console.log(`  Immediately after 10 burst widgets on maxDockWidgets=2: size = ${wmSmall.widgets.size}`);
  await new Promise((resolve) => setTimeout(resolve, 450));
  console.log(`  450ms after burst on maxDockWidgets=2: size = ${wmSmall.widgets.size} (keys: ${Array.from(wmSmall.widgets.keys())})`);
  if (wmSmall.widgets.size !== 2) throw new Error(`Expected size 2, got ${wmSmall.widgets.size}`);
  if (!wmSmall.widgets.has('fast_9') || !wmSmall.widgets.has('fast_10')) {
    throw new Error(`Expected fast_9 and fast_10 to survive, got ${Array.from(wmSmall.widgets.keys())}`);
  }

  // 13.4 Pulse element throttling under 1,000 rapid updates
  const singleWidget = wm.renderWidget({ id: 'perf_widget', target: 'dock', template: 'telemetry' });
  const t0 = Date.now();
  for (let i = 0; i < 1000; i++) {
    wm.updateWidget('perf_widget', { cpu: i % 100 });
  }
  const dt = Date.now() - t0;
  console.log(`  1,000 updates executed in ${dt}ms (${(1000 / (dt || 1) * 1000).toFixed(0)} updates/sec)`);
  if (!singleWidget.containerEl.classList.contains('gen-ui-pulse')) {
    throw new Error('Expected gen-ui-pulse to be active on container element');
  }

  console.log('\n✓ ALL DEEP HARDENING VERIFICATIONS PASSED SUCCESSFULLY!');
}

runDeepHardening().catch(err => {
  console.error('Deep hardening test failed:', err);
  process.exit(1);
});
