// Empirical verification script for Explorer 2's proposed WidgetManager fixes
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const htmlPath = path.resolve('C:/jarvis/Mark-LV-main/Mark-LV-main/ui_improved.html');
let htmlContent = fs.readFileSync(htmlPath, 'utf8');

// Detect line ending
const hasCrlf = htmlContent.includes('\r\n');
console.log('File line endings:', hasCrlf ? 'CRLF' : 'LF');

// Normalize to LF for easy manipulation, then convert back if needed
const normalizedHtml = htmlContent.replace(/\r\n/g, '\n');

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

console.log('Checking chunk replacements in normalized memory:');
console.log('1. renderWidget chunk found:', normalizedHtml.includes(originalRenderChunk));
console.log('2. dismissWidget chunk found:', normalizedHtml.includes(originalDismissChunk));
console.log('3. clearAll chunk found:', normalizedHtml.includes(originalClearAllChunk));
console.log('4. _pulseElement chunk found:', normalizedHtml.includes(originalPulseChunk));

if (!normalizedHtml.includes(originalRenderChunk) ||
    !normalizedHtml.includes(originalDismissChunk) ||
    !normalizedHtml.includes(originalClearAllChunk) ||
    !normalizedHtml.includes(originalPulseChunk)) {
  console.error('ERROR: One or more chunks not found in ui_improved.html');
  process.exit(1);
}

let patchedNormalizedHtml = normalizedHtml
  .replace(originalRenderChunk, proposedRenderChunk)
  .replace(originalDismissChunk, proposedDismissChunk)
  .replace(originalClearAllChunk, proposedClearAllChunk)
  .replace(originalPulseChunk, proposedPulseChunk);

const patchedFinalHtml = hasCrlf
  ? patchedNormalizedHtml.replace(/\n/g, '\r\n')
  : patchedNormalizedHtml;

// Now load and run the oracle test using patchedFinalHtml!
const oraclePath = path.resolve('C:/jarvis/Mark-LV-main/Mark-LV-main/tests/test_widget_manager_oracle.js');
let oracleCode = fs.readFileSync(oraclePath, 'utf8');

// Replace fs.readFileSync(htmlPath, 'utf8') with patchedFinalHtml in oracle setupEnvironment
oracleCode = oracleCode.replace(
  "const htmlContent = fs.readFileSync(htmlPath, 'utf8');",
  "const htmlContent = patchedHtml;"
);

const sandbox = {
  require: require,
  __dirname: path.dirname(oraclePath),
  console: console,
  setTimeout: setTimeout,
  clearTimeout: clearTimeout,
  process: process,
  patchedHtml: patchedFinalHtml
};

vm.runInNewContext(oracleCode, sandbox);
