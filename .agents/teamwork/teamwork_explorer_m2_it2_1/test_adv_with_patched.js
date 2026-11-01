const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert');

// Test that our hardened WidgetTemplates and _generateHtml passes adversarial_test.js completely!
const advPath = path.resolve(__dirname, '..', 'teamwork_reviewer_m2_2', 'adversarial_test.js');
let advCode = fs.readFileSync(advPath, 'utf8');

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

let patchedHtml = html.slice(0, origWtStart) + wtCode + '\n\n    window.WidgetTemplates = WidgetTemplates;' + html.slice(origWtEnd);

// Modify adversarial test to use patchedHtml
const modifiedAdv = advCode.replace(
  "const html = fs.readFileSync(htmlPath, 'utf8');",
  "const html = global.__patchedHtml;"
);

global.__patchedHtml = patchedHtml;

const script = new vm.Script(modifiedAdv, { filename: 'adversarial_test.js' });
const context = vm.createContext({
  ...global,
  require: require,
  __dirname: path.dirname(advPath),
  __filename: advPath,
  process: process,
  console: console,
  setTimeout: setTimeout,
  clearTimeout: clearTimeout
});

script.runInContext(context);
