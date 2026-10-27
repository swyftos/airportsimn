// App wiring smoke test without a browser. This exercises the real app/model/ledger
// against a minimal DOM adapter; it does not verify CSS layout or WebGL rendering.
import assert from 'node:assert/strict';
import fs from 'node:fs';
const data = JSON.parse(fs.readFileSync(new URL('./parking_data.json', import.meta.url)));
const html = fs.readFileSync(new URL('./index.html', import.meta.url), 'utf8');
const nodes = new Map();
class Element {
  constructor() {
    this.dataset = {}; this.value = ''; this.hidden = false; this.listeners = {}; this.attributes = {};
    this.style = { setProperty() {} };
    const classes = new Set();
    this.classList = { contains: value => classes.has(value), add: value => classes.add(value), remove: value => classes.delete(value),
      toggle(value, force = !classes.has(value)) { if (force) classes.add(value); else classes.delete(value); return force; } };
  }
  set innerHTML(value) { this.markup = value; registerIds(value); }
  get innerHTML() { return this.markup || ''; }
  setAttribute(name, value) { this.attributes[name] = value; }
  getAttribute(name) { return this.attributes[name]; }
  addEventListener(name, handler) { (this.listeners[name] ||= []).push(handler); }
  emit(name, target = this) { for (const listener of this.listeners[name] || []) listener({ target, preventDefault() {} }); }
  querySelectorAll() { return []; }
  getBoundingClientRect() { return { height: this.hidden ? 0 : 100 }; }
  replaceChildren() { this.innerHTML = ''; }
  focus() {}
  prepend() {}
}
function registerIds(markup) {
  for (const match of markup.matchAll(/\bid="([^"]+)"/g)) if (!nodes.has('#' + match[1])) nodes.set('#' + match[1], new Element());
}
registerIds(html);
for (const name of ['#impact-grid-table thead', '.gauge', '.waiting-readout', '.camera-controls', '#plan-impact .impact-stat:last-of-type strong', '#plan-impact .impact-stat:last-of-type span']) nodes.set(name, new Element());
const cameras = [...html.matchAll(/data-camera="([^"]+)"/g)].map(match => { const el = new Element(); el.dataset.camera = match[1]; nodes.set(`[data-camera="${match[1]}"]`, el); return el; });
const querySelector = selector => {
  if (selector.startsWith('[data-preview-') || selector === '[data-model-call="true"]') return new Element();
  return nodes.get(selector) || null;
};
const document = Object.assign(new Element(), { querySelector, querySelectorAll: selector => selector === '[data-camera]' ? cameras : [],
  documentElement: new Element(), body: new Element(), hidden: false });
let reduced = false;
const window = Object.assign(new Element(), { matchMedia: query => ({ matches: query.includes('reduced-motion') && reduced, addEventListener() {} }) });
const storage = new Map();
Object.assign(globalThis, { document, window, localStorage: { getItem: key => storage.get(key) || null, setItem: (key, value) => storage.set(key, value), removeItem: key => storage.delete(key) },
  ResizeObserver: class { observe() {} }, requestAnimationFrame: () => 1, cancelAnimationFrame() {},
  fetch: async () => ({ ok: true, json: async () => data }) });
await import('./app.js');
// main() fetches data and dynamically imports Three.js; the unavailable CDN import
// intentionally drives the supported WebGL fallback path in this Node test.
for (let tries = 0; tries < 100 && !nodes.get('#scrub').listeners.input; tries++) await new Promise(resolve => setTimeout(resolve, 5));
assert.ok(nodes.get('#scrub').listeners.input, `App initialized: ${nodes.get('#summary-copy').textContent}`);
assert.doesNotMatch(nodes.get('#summary-copy').textContent, /could not|Cannot|HTTP hosting/);
assert.ok(nodes.get('#view-context').textContent.includes(data.scenarios[data.default_scenario] ? data.default_scenario : 'missing'));
assert.ok(nodes.get('#view-context').textContent.includes(data.situations[data.situation_outlook.base_case]));
assert.equal(nodes.get('#whatif-banner').hidden, true);
function preview(situation, scenario) {
  const target = { dataset: { previewSituation: situation, previewScenario: scenario }, closest: () => target };
  nodes.get('#impact-grid-tbody').emit('click', target);
}
function scrub(tick) { nodes.get('#scrub').value = String(tick); nodes.get('#scrub').emit('input'); }
for (const situation of Object.keys(data.situations)) for (const scenario of Object.keys(data.scenarios)) {
  preview(situation, scenario);
  const model = situation === data.situation_outlook.base_case && scenario === data.default_scenario;
  assert.equal(nodes.get('#whatif-banner').hidden, model);
  if (!model) assert.equal(nodes.get('#whatif-text').textContent, `What-if: ${data.situations[situation]}, ${scenario} demand. Not the model's call`);
  assert.equal((nodes.get('#flow-plan-tbody').innerHTML.match(/data-flow-date=/g) || []).length, data.days.length);
  assert.ok(nodes.get('#hud-view-context').textContent.includes(scenario));
  assert.ok(nodes.get('#hud-view-context').textContent.includes(data.situations[situation]));
  // Every day can be reached after changing the scenario with the existing layout.
  data.days.forEach((day, index) => {
    scrub(index * 24 + 13);
    assert.ok(nodes.get('#forecast-table').innerHTML.includes(data.parking[situation].days[scenario][day.date].parking_demand_su_p50.toFixed(1)));
    assert.ok(nodes.get('#stand-register').innerHTML.includes('<tr>'));
  });
}
nodes.get('#whatif-back-btn').emit('click');
assert.equal(nodes.get('#whatif-banner').hidden, true);
const pause = data.situation_outlook.items.find(item => item.situation === data.situation_outlook.base_case);
const gameIndex = data.days.findIndex(day => pause.dates.includes(day.date));
const hour = value => { const [h, m] = value.split(':').map(Number); return h + m / 60; };
for (const [at, visible] of [[hour(pause.window[0]) - 1 / 60, false], [hour(pause.window[0]), true], [hour(pause.window[1]) - 1 / 60, true], [hour(pause.window[1]), false]]) {
  scrub(gameIndex * 24 + at);
  assert.equal(!nodes.get('#pause-stage-banner').hidden, visible, `Banner at ${at}`);
}
// Named approvals remain scoped to a situation/scenario, with Undo.
nodes.get('#manager-name-input').value = 'Smoke test manager';
const clickAction = selector => nodes.get('#actions').emit('click', { closest: candidate => candidate === selector ? {} : null });
clickAction('#approve-plan-btn');
assert.match(nodes.get('#actions').innerHTML, /Approved by Smoke test manager/);
assert.match(nodes.get('#remote-label').textContent, /approved today/);
preview('heavy_rain', 'High');
assert.match(nodes.get('#remote-label').textContent, /No approved/);
nodes.get('#whatif-back-btn').emit('click');
assert.match(nodes.get('#actions').innerHTML, /Approved by Smoke test manager/);
clickAction('#btn-undo-plan');
assert.match(nodes.get('#remote-label').textContent, /No approved/);
console.log('PASS: app initialization, 12 previews, synchronized day/overlay/table/register, return to model, minute-level pause banner, scoped named approvals and Undo (DOM adapter; no visual/WebGL QA).');
