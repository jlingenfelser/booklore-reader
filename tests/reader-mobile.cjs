// Run after source preparation: node tests/reader-mobile.cjs [typescript module path]
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require(process.argv[2] || '../.build/booklore-src/booklore-ui/node_modules/typescript');
const root = process.env.READER_UI_ROOT || '.build/booklore-src/booklore-ui/';
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
  const resizeStart = paginator.indexOf('    #resizeInlineSize');
  const resizeEnd = paginator.indexOf('    #top', resizeStart);
  const restoreStart = paginator.indexOf("    async #scrollToAnchor(anchor, reason = 'anchor')");
  const restoreEnd = paginator.indexOf('    #getVisibleRange()', restoreStart);
  const Layout = vm.runInNewContext(`class Layout {
    #container = {scrollTop: 200, scrollLeft: 0,
      getBoundingClientRect: () => this.bounds};
    #vertical = false; #view = {}; #lastAnchorOffset = 200; #anchor = 'saved';
    bounds = {width: 390, height: 700}; scrolled = true; scrollProp = 'scrollTop';
    renders = 0; restores = []; relocations = [];
    ${paginator.slice(resizeStart, resizeEnd)}
    ${paginator.slice(restoreStart, restoreEnd)}
    render() { this.renders++; }
    #afterScroll(reason) {
      this.relocations.push(reason);
      this.#lastAnchorOffset = this.#container[this.scrollProp];
    }
    #scrollToRect(rect, reason) { this.restores.push(reason); }
    #scrollTo(offset, reason) { this.restores.push(reason); }
    #scrollToPage(page, reason) { this.restores.push(reason); }
    resize(width, height) { this.bounds = {width, height}; this.#observer.callback(); }
    move(offset) { this.#container[this.scrollProp] = offset; }
    restore(reason) { return this.#scrollToAnchor(0.5, reason); }
    vertical() { this.#vertical = true; this.scrollProp = 'scrollLeft'; }
  }; Layout`, {
    ResizeObserver: class { constructor(callback) { this.callback = callback; } },
    uncollapse: () => null,
  });
  const layout = new Layout();
  layout.resize(390, 700);
  layout.resize(390, 780);
  layout.resize(390, 700);
  assert.equal(layout.renders, 1, 'browser toolbar height changes must not restore position');
  layout.resize(780, 390);
  assert.equal(layout.renders, 2, 'orientation/width changes must still reflow');
  layout.scrolled = false;
  layout.resize(780, 400);
  assert.equal(layout.renders, 3, 'paginated mode must still render on height changes');
  const vertical = new Layout();
  vertical.vertical();
  vertical.resize(390, 700);
  vertical.resize(450, 700);
  assert.equal(vertical.renders, 1, 'vertical text uses height as its layout axis');
  vertical.resize(450, 800);
  assert.equal(vertical.renders, 2);
  for (const offset of [100, 300]) {
    const pending = new Layout();
    pending.move(offset);
    await pending.restore();
    assert.equal(pending.restores.length, 0, 'pending native scroll must win in either direction');
    assert.equal(pending.relocations.length, 1, 'pending position must update reading progress');
    await pending.restore('navigation');
    await pending.restore('selection');
    assert.equal(pending.restores.length, 2, 'explicit navigation and selection must still work');
  }
  const stationary = new Layout();
  await stationary.restore();
  assert.equal(stationary.restores.length, 1, 'stationary content expansion retains restoration');
  console.log('Mobile reader regression checks passed.');
})().catch(error => { console.error(error); process.exitCode = 1; });
