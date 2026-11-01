const fs = require('fs');
const path = require('path');
const vm = require('vm');

const oraclePath = path.resolve(__dirname, '..', '..', '..', 'tests', 'test_widget_manager_oracle.js');
let oracleCode = fs.readFileSync(oraclePath, 'utf8');

const htmlPath = path.resolve(__dirname, '..', '..', '..', 'ui_improved.html');
let html = fs.readFileSync(htmlPath, 'utf8');

const hardenedJs = fs.readFileSync(path.resolve(__dirname, 'verify_hardening.js'), 'utf8');
const wtCode = hardenedJs.slice(
  hardenedJs.indexOf('const WidgetTemplates = {'),
  hardenedJs.indexOf('// Simulation of _generateHtml')
).trim();

// Replace WidgetTemplates
const origWtStart = html.indexOf('const WidgetTemplates = {');
const origWtEnd = html.indexOf('window.WidgetTemplates = WidgetTemplates;', origWtStart) + 'window.WidgetTemplates = WidgetTemplates;'.length;
if (origWtStart === -1) throw new Error('WT not found in html');

let patchedHtml = html.slice(0, origWtStart) + wtCode + '\n\n    window.WidgetTemplates = WidgetTemplates;' + html.slice(origWtEnd);

// Replace _generateHtml
const origGenStart = patchedHtml.indexOf('_generateHtml(schema, widgetId, templateName) {');
const wmInstStart = patchedHtml.indexOf('const widgetManager = new WidgetManager({', origGenStart);
// Find the closing brace of _generateHtml before wmInstStart
const origGenEnd = patchedHtml.lastIndexOf('}', patchedHtml.lastIndexOf('}', wmInstStart - 1) - 1) + 1;

console.log('origGenStart:', origGenStart, 'origGenEnd:', origGenEnd);
console.log('Replacing chunk:', JSON.stringify(patchedHtml.slice(origGenStart, origGenEnd)));

const newGenHtml = `_generateHtml(schema, widgetId, templateName) {
        try {
          const tplDef = this.templates.get(templateName);
          if (tplDef && typeof tplDef.render === 'function') {
            return tplDef.render(schema);
          }
          if (typeof window !== 'undefined' && window.WidgetTemplates && typeof window.WidgetTemplates[templateName] === 'function') {
            return window.WidgetTemplates[templateName](schema);
          }
          const safeTitle = (typeof window !== 'undefined' && window.WidgetTemplates && typeof window.WidgetTemplates._escape === 'function')
            ? window.WidgetTemplates._escape(schema.title || widgetId)
            : String(schema.title || widgetId).replace(/[&<>"']/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m]));
          return \`<div class="gen-ui-card"><div class="gen-ui-title">\${safeTitle}</div></div>\`;
        } catch (err) {
          console.error(\`[WidgetManager] Error rendering template '\${templateName}' for widget '\${widgetId}':\`, err);
          const safeId = (typeof window !== 'undefined' && window.WidgetTemplates && typeof window.WidgetTemplates._escape === 'function')
            ? window.WidgetTemplates._escape(schema && schema.title ? schema.title : widgetId)
            : String(widgetId).replace(/[&<>"']/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m]));
          const safeMsg = String(err && err.message ? err.message : 'Render Error').replace(/[&<>"']/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m]));
          return \`
            <div class="gen-ui-header">
              <div class="gen-ui-title-group">
                <span class="gen-ui-title">\${safeId}</span>
              </div>
              <div class="gen-ui-controls">
                <span class="gen-ui-badge danger">ERROR</span>
                <button class="gen-ui-close-btn" data-action-id="dismiss" data-widget-dismiss aria-label="Dismiss">✕</button>
              </div>
            </div>
            <div class="gen-card-body">
              <div class="gen-ui-metric-label" style="color: var(--amber, #f87171);">\${safeMsg}</div>
            </div>
          \`;
        }
      }`;

patchedHtml = patchedHtml.slice(0, origGenStart) + newGenHtml + patchedHtml.slice(origGenEnd);

const modifiedOracle = oracleCode.replace(
  "const htmlContent = fs.readFileSync(htmlPath, 'utf8');",
  "const htmlContent = global.__patchedHtml;"
);

global.__patchedHtml = patchedHtml;

const script = new vm.Script(modifiedOracle, { filename: 'test_widget_manager_oracle.js' });
const context = vm.createContext({
  ...global,
  require: require,
  __dirname: path.dirname(oraclePath),
  __filename: oraclePath,
  process: process,
  console: console,
  setTimeout: setTimeout,
  clearTimeout: clearTimeout
});

script.runInContext(context);
