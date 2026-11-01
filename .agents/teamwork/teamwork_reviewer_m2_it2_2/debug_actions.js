const fs = require('fs');
const path = require('path');
const vm = require('vm');
const html = fs.readFileSync('C:/jarvis/Mark-LV-main/Mark-LV-main/ui_improved.html', 'utf8');
const startToken = 'const WidgetTemplates =';
const endToken = 'window.widgetManager = widgetManager;';
const startIndex = html.indexOf(startToken);
const endIndex = html.indexOf(endToken, startIndex) + endToken.length;
const jsCode = html.slice(startIndex, endIndex);
const sb = { window: {}, document: { createElement: () => ({ classList: { add: () => {} } }), getElementById: () => null, querySelector: () => null } };
sb.window = sb;
vm.createContext(sb);
vm.runInContext(jsCode, sb);
const WT = sb.WidgetTemplates;
const payloads = [
  '<script>alert("xss")</script>',
  '"><script>alert(1)</script>',
  '\'><script>alert(2)</script>',
  '"><img src=x onerror=alert(3)>',
  '\' onfocus=\'alert(4)\'',
  'javascript:alert(5)',
  '<svg/onload=alert(6)>',
  '"><iframe src="javascript:alert(7)"></iframe>'
];
payloads.forEach(p => {
  const out = WT.renderActions('w1', [{ action_id: 'a1', label: 'L', variant: p }]);
  console.log('PAYLOAD:', p);
  console.log('OUTPUT:', out);
});
