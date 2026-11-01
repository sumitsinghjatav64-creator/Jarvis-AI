const fs = require('fs');
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
const out = WT.telemetry({
  id: 'test_telem',
  template: 'telemetry',
  title: 'Test',
  data: {
    metrics: [{ id: '<script>alert("xss")</script>', label: '<script>alert("xss")</script>', value: 50 }]
  }
});
console.log('Contains unescaped <script>:', out.includes('<script>'));
console.log('Contains escaped &lt;script&gt;:', out.includes('&lt;script&gt;'));
