const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

class Element {
  constructor(tag) {
    this.tagName = tag; this.children = []; this.style = {}; this.events = {};
    this.className = ''; this.textContent = ''; this.value = ''; this.disabled = false;
    this.classList = { add() {}, toggle() {} };
  }
  appendChild(child) { this.children.push(child); return child; }
  append(...children) { this.children.push(...children); }
  addEventListener(name, fn) { this.events[name] = fn; }
  setAttribute(name, value) { this[name] = value; }
}
const source = fs.readFileSync(path.join(__dirname, 'ui.js'), 'utf8');
const start = source.indexOf('function buildHistoryRow(item)');
const end = source.indexOf('function traceItem(', start);
assert.ok(start >= 0 && end > start);
let confirmChoice = false, calls = [], messages = [], reloads = 0, fail = false;
const context = {
  document: { createElement: tag => new Element(tag), createTextNode: text => ({textContent: text}) },
  _speakersCache: [{name: 'Jaco'}, {name: 'Ed'}],
  formatDateTime: text => text, formatDuration: duration => `${duration}ms`,
  makePlayBtn: () => new Element('button'), traceItem: () => new Element('div'),
  window: { confirm: () => confirmChoice },
  showToast: text => messages.push(text), loadHistory: async () => { reloads++; },
  apiFetch: async (url, options) => {
    calls.push({url, payload: JSON.parse(options.body)});
    if (fail) throw new Error('This recording changed');
    return {cache_refresh_requested: true};
  },
};
vm.createContext(context);
vm.runInContext(source.slice(start, end), context);
function find(node, pred) {
  if (pred(node)) return node;
  for (const child of node.children || []) { const found = find(child, pred); if (found) return found; }
}
function row(overrides = {}) {
  return context.buildHistoryRow({id: 'i', recorded_at: 'time', transcript: 'hello', duration_ms: 800,
    matched_speaker: 'Jaco', match_confidence: .48, vad_confidence: .8,
    status: 'resolved', audio_url: '/audio/i', current_resolution_id: 'r1',
    current_action: 'assign', current_assigned_to: 'Jaco', last_resolved_at: null, ...overrides});
}

(async () => {
  const view = row();
  const select = find(view, e => e.tagName === 'select');
  const save = find(view, e => e.textContent === 'Save correction');
  assert.ok(select && save);
  assert.ok(select.children.some(e => e.value === 'speaker:Ed'));
  assert.ok(!select.children.some(e => e.value === 'speaker:Jaco'));
  select.value = 'speaker:Ed';
  await save.events.click();
  assert.equal(calls.length, 0, 'cancel must not submit');
  confirmChoice = true;
  await save.events.click();
  assert.equal(calls[0].url, '/interactions/i/correct');
  assert.deepEqual(calls[0].payload, {assigned_to: 'Ed', expected_resolution_id: 'r1'});
  assert.equal(reloads, 1);

  const undoView = row();
  const undo = find(undoView, e => e.tagName === 'select');
  const undoSave = find(undoView, e => e.textContent === 'Save correction');
  undo.value = 'unknown:';
  await undoSave.events.click();
  assert.equal(calls[1].payload.assigned_to, null);

  fail = true;
  const staleView = row();
  const staleSelect = find(staleView, e => e.tagName === 'select');
  const staleSave = find(staleView, e => e.textContent === 'Save correction');
  staleSelect.value = 'speaker:Ed';
  await staleSave.events.click();
  assert.equal(staleSave.disabled, false);
  assert.ok(messages.at(-1).includes('This recording changed'));

  const reassigned = row({current_assigned_to: 'Ed'});
  assert.equal(find(reassigned, e => e.className === 'history-speaker').textContent, 'Ed');
  const unassigned = row({current_action: 'dismiss', current_assigned_to: null, status: 'pending'});
  assert.equal(find(unassigned, e => e.className === 'history-speaker').textContent, 'Unknown');
  assert.equal(find(row({audio_url: null}), e => e.textContent === 'Save correction'), undefined);
  console.log('History correction UI: passed');
})().catch(err => { console.error(err); process.exitCode = 1; });
