// Run after source preparation: node tests/reader-mobile.cjs [typescript module path]
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require(process.argv[2] || '../.build/booklore-src/booklore-ui/node_modules/typescript');
const root = '.build/booklore-src/booklore-ui/';
const reader = fs.readFileSync(root + 'src/app/features/readers/ebook-reader/ebook-reader.component.ts', 'utf8');
const methods = reader.slice(reader.indexOf("  @HostListener('document:visibilitychange')"), reader.indexOf('  toggleTtsTapToStart():'))
  .replace(/  @HostListener\([^\n]+\)\n/g, '');
const context = {document: {visibilityState: 'visible'}, navigator: {}, console: {warn() {}}};
const Reader = vm.runInNewContext(ts.transpile(`class Reader {
  ttsKeepAwake = true; ttsSessionId = 1; ttsWakeLock = null; ttsWakeLockRequest = null;
  ${methods}
}; Reader`, {target: ts.ScriptTarget.ES2022}), context);
function lock() {
  return {released: false, addEventListener(type, cb) { this.onrelease = cb; },
    async release() { this.released = true; this.onrelease?.(); }};
}
(async () => {
  let calls = 0;
  let current;
  context.navigator.wakeLock = {async request() { calls++; return current = lock(); }};
  const r = new Reader();
  await Promise.all([r.requestTtsWakeLock(), r.requestTtsWakeLock()]);
  assert.equal(calls, 1, 'concurrent requests share a lock');
  assert.equal(r.ttsWakeLock, current);
  await current.release();
  await r.requestTtsWakeLock();
  assert.equal(calls, 2, 'released locks can be reacquired');
  r.releaseTtsWakeLock();
  assert.equal(current.released, true);
  assert.equal(r.ttsKeepAwake, false);

  let resolve;
  context.navigator.wakeLock.request = () => new Promise(done => resolve = done);
  const stopped = new Reader();
  const pending = stopped.requestTtsWakeLock();
  stopped.releaseTtsWakeLock();
  stopped.ttsSessionId++;
  const late = lock();
  resolve(late);
  await pending;
  assert.equal(late.released, true, 'late grant after stop must be released');
  assert.equal(stopped.ttsWakeLock, null);

  context.navigator.wakeLock.request = async () => { throw Error('denied'); };
  const denied = new Reader();
  await denied.requestTtsWakeLock();
  assert.equal(denied.ttsWakeLockRequest, null, 'denial must not block playback or future requests');
  context.document.visibilityState = 'hidden';
  context.navigator.wakeLock.request = () => { throw Error('hidden request'); };
  await new Reader().requestTtsWakeLock();

  delete context.navigator.wakeLock;
  context.document.visibilityState = 'visible';
  await new Reader().requestTtsWakeLock();

  const paginator = fs.readFileSync(root + 'src/assets/foliate/paginator.js', 'utf8');
  const start = paginator.indexOf("        this.#container.addEventListener('scroll', () => {");
  const end = paginator.indexOf("        this.#container.addEventListener('scroll', debounce", start);
  assert.ok(start >= 0 && end > start);
  const Paginator = vm.runInNewContext(`class Paginator {
    #container = {scrollTop: 0, addEventListener: (type, cb) => this.scroll = cb};
    #view = {}; #anchor = 'navigation'; #lastAnchorOffset = 0; #justAnchored = true;
    scrolled = true; scrollProp = 'scrollTop';
    #getVisibleRange() { return 'current'; }
    dispatchEvent() {}
    constructor() { ${paginator.slice(start, end)} }
    move(offset) { this.#container.scrollTop = offset; this.scroll(); }
    get anchor() { return this.#anchor; }
    get justAnchored() { return this.#justAnchored; }
  }; Paginator`, {Event: class {}});
  const p = new Paginator();
  p.move(0);
  assert.equal(p.anchor, 'navigation', 'programmatic scroll preserves exact anchor');
  p.move(100);
  assert.equal(p.anchor, 'current', 'manual scroll updates anchor before debounce/resize');
  assert.equal(p.justAnchored, false, 'first manual scroll must not be skipped');
  const paginated = new Paginator();
  paginated.scrolled = false;
  paginated.move(100);
  assert.equal(paginated.anchor, 'navigation', 'paginated behavior stays unchanged');
  console.log('Mobile reader regression checks passed.');
})().catch(error => { console.error(error); process.exitCode = 1; });
