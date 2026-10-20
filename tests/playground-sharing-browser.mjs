import assert from 'node:assert/strict';
import { createReadStream } from 'node:fs';
import { mkdir, readFile, stat, writeFile } from 'node:fs/promises';
import { createServer } from 'node:http';
import path from 'node:path';
import { performance } from 'node:perf_hooks';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { createShareURL, encodeShareFragment, readShareURL, SHARE_FRAGMENT_LIMIT } from '../playground/share.mjs';
import { tour } from '../playground/tour.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));
const site = path.resolve(root, process.env.MINYAR_PLAYGROUND_DIR ?? 'build/playground');
const evidence = path.resolve(root, process.env.MINYAR_WASM_EVIDENCE ?? 'build/wasm-evidence');
const dependency = path.join(root, 'build/playground-tests/node_modules/playwright/index.mjs');
const { chromium } = await import(pathToFileURL(dependency).href);
const packageInfo = JSON.parse(await readFile(path.join(path.dirname(dependency), 'package.json'), 'utf8'));
const expectedVersion = JSON.parse(await readFile(new URL('../playground/test-package.json', import.meta.url), 'utf8')).devDependencies.playwright;
assert.equal(packageInfo.version, expectedVersion, 'sharing checks require the pinned Chromium harness');
await stat(path.join(site, 'index.html'));
await mkdir(evidence, { recursive: true });

const mount = '/nested/try/';
const requests = [], failures = [], pageErrors = [], externalRequests = [];
const checks = [];
const report = { startedAt: new Date().toISOString(), playwright: packageInfo.version, checks };
const mime = { '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8', '.mjs': 'application/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8', '.wasm': 'application/wasm' };
const server = createServer(async (request, response) => {
  requests.push(request.url);
  try {
    if (!['GET', 'HEAD'].includes(request.method)) throw new Error('Unsupported method');
    const url = new URL(request.url, 'http://localhost');
    if (!url.pathname.startsWith(mount)) throw new Error('Request escaped the mounted playground');
    const suffix = decodeURIComponent(url.pathname.slice(mount.length) || 'index.html');
    const filename = path.resolve(site, suffix);
    if (!filename.startsWith(site + path.sep)) throw new Error('Unsafe path');
    const info = await stat(filename);
    if (!info.isFile()) throw new Error('Not a file');
    response.setHeader('Content-Type', mime[path.extname(filename)] ?? 'application/octet-stream');
    response.setHeader('Content-Length', info.size);
    response.setHeader('Cache-Control', 'no-store');
    response.writeHead(200);
    if (request.method === 'HEAD') response.end();
    else createReadStream(filename).on('error', error => response.destroy(error)).pipe(response);
  } catch (error) {
    failures.push({ url: request.url, message: error.message });
    if (!response.headersSent) response.writeHead(404);
    response.end('Not found');
  }
});
await new Promise((resolve, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolve); });
const origin = `http://127.0.0.1:${server.address().port}`;
const baseURL = origin + mount;
const draftSource = 'print("A private local draft.")\n';
const privateMarker = 'PRIVATE_SHARED_SOURCE_20261020';
const sharedSource = `// ${privateMarker}\nprint("A shared harbour. 🌙")\n`;
let browser, currentPage;

function observeAndSeed({ draft, seedOnce }) {
  window.__sharingRequests = [];
  window.__sharingWorkers = 0;
  const NativeWorker = window.Worker;
  window.Worker = class extends NativeWorker {
    constructor(...args) { super(...args); window.__sharingWorkers++; }
    postMessage(...args) { window.__sharingRequests.push(args[0]); return super.postMessage(...args); }
  };
  try {
    if (location.protocol === 'http:' && (!seedOnce || localStorage.getItem('minyar.test.sharing.seeded') !== '1')) {
      localStorage.setItem('minyar.playground.draft.v1', JSON.stringify({ version: 1, exampleId: 'hello', source: draft }));
      if (seedOnce) localStorage.setItem('minyar.test.sharing.seeded', '1');
    }
  } catch {}
}

async function contextFor(name, { seedOnce = false } = {}) {
  const context = await browser.newContext({ permissions: ['clipboard-read', 'clipboard-write'], viewport: { width: 1280, height: 1000 } });
  await context.addInitScript(observeAndSeed, { draft: draftSource, seedOnce });
  context.on('request', request => {
    const url = new URL(request.url());
    if (['http:', 'https:'].includes(url.protocol) && url.origin !== origin) externalRequests.push({ name, url: request.url() });
  });
  context.on('page', page => {
    page.setDefaultTimeout(15_000);
    page.on('pageerror', error => pageErrors.push({ name, message: error.message }));
  });
  return context;
}

async function open(context, url = baseURL) {
  const page = await context.newPage();
  currentPage = page;
  const response = await page.goto(url, { waitUntil: 'load' });
  assert.equal(response.status(), 200);
  await page.locator('#share').waitFor({ state: 'visible' });
  return page;
}

async function sourceEquals(page, source) {
  await page.waitForFunction(expected => document.getElementById('source')?.value === expected, source);
  assert.equal(await page.locator('#source').inputValue(), source);
}

async function noAutomaticWork(page) {
  // One observation window spans the editor's debounce. It catches delayed
  // checks too, rather than asserting only the initial synchronous state.
  await page.evaluate(() => new Promise(resolve => setTimeout(resolve, 850)));
  assert.equal(await page.evaluate(() => window.__sharingWorkers), 0, 'loading a link must not construct a compiler worker');
  assert.deepEqual(await page.evaluate(() => window.__sharingRequests), [], 'loading a link must not check or execute code');
  assert.equal(await page.locator('#output').textContent(), '');
}

async function settledFrames(page) {
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
}

async function measure(name, action) {
  const started = performance.now();
  await action();
  checks.push({ name, durationMs: Math.round(performance.now() - started) });
  console.log(`PASS sharing-browser/${name}`);
}

try {
  browser = await chromium.launch({ headless: true, timeout: 30_000, args: ['--no-sandbox'] });
  report.browser = browser.version();
  const primary = await contextFor('primary');
  const sharedURL = await createShareURL(baseURL + '?tracking=old#stale', sharedSource, { exampleId: 'functions' });
  const page = await open(primary, sharedURL);
  let copiedURL;

  await measure('valid fragment overrides draft without automatic compiler work', async () => {
    await sourceEquals(page, sharedSource);
    assert.match(await page.locator('.tour-button[aria-current="step"]').textContent(), new RegExp(tour[1].title));
    await noAutomaticWork(page);
    assert.equal(await page.evaluate(() => JSON.parse(localStorage.getItem('minyar.playground.draft.v1')).source), draftSource,
      'viewing a shared program must not overwrite the prior local draft');
  });

  await measure('Share copies a private link and exposes a readonly fallback', async () => {
    await page.locator('#share').click();
    const field = page.locator('#share-url');
    await field.waitFor({ state: 'visible' });
    await page.waitForFunction(() => document.getElementById('share-url').value.includes('#minyar='));
    copiedURL = await field.inputValue();
    assert.equal(await field.getAttribute('readonly') !== null, true);
    const parsed = new URL(copiedURL);
    assert.equal(parsed.origin, origin);
    assert.equal(parsed.pathname, mount);
    assert.equal(parsed.search, '');
    assert.ok(parsed.hash.startsWith('#minyar=v1.u.'));
    await page.locator('#share-message').filter({ hasText: /copied/i }).waitFor();
    const clipboard = await page.evaluate(() => navigator.clipboard.readText());
    assert.equal(clipboard, copiedURL, 'the actual clipboard must receive the displayed link');
    assert.match(await page.locator('#share-message').textContent(), /copied|link|share|ready/i);
  });

  await measure('copied link and reload preserve the shared program over drafts', async () => {
    const reopened = await open(primary, copiedURL);
    await sourceEquals(reopened, sharedSource);
    await noAutomaticWork(reopened);
    await reopened.reload({ waitUntil: 'load' });
    await sourceEquals(reopened, sharedSource);
    await noAutomaticWork(reopened);
    await reopened.close();
  });

  await measure('hash navigation loads new programs and browser history restores them', async () => {
    const second = 'print("Second shared thought. 🚀")\n';
    const fragment = await encodeShareFragment(second, { exampleId: 'hello' });
    await page.evaluate(hash => { location.hash = hash; }, fragment);
    await sourceEquals(page, second);
    await noAutomaticWork(page);
    await page.goBack({ waitUntil: 'load' });
    await sourceEquals(page, sharedSource);
    await page.goForward({ waitUntil: 'load' });
    await sourceEquals(page, second);
    await noAutomaticWork(page);
  });

  await measure('invalid initial fragment keeps the local draft and explains the problem', async () => {
    const invalid = await open(primary, baseURL + '#minyar=v2.u.0.00000000.');
    await sourceEquals(invalid, draftSource);
    await invalid.locator('#share-message').filter({ hasText: /newer|format|updated|unsupported/i }).waitFor();
    await noAutomaticWork(invalid);
    await invalid.close();
  });

  await measure('an oversized rejected fragment cannot prevent sharing the valid draft', async () => {
    const oversized = '#minyar=' + 'A'.repeat(SHARE_FRAGMENT_LIMIT + 16 * 1024 + 1);
    const rejected = await open(primary, baseURL + '?tracking=discard-this' + oversized);
    await sourceEquals(rejected, draftSource);
    await rejected.locator('#share-message').filter({ hasText: /64\s*KiB|too (?:long|large)|limit/i }).waitFor();
    await noAutomaticWork(rejected);
    await rejected.locator('#share').click();
    await rejected.locator('#share-url').waitFor({ state: 'visible' });
    await rejected.locator('#share-message').filter({ hasText: /copied/i }).waitFor();
    const generated = await rejected.locator('#share-url').inputValue();
    const parsed = new URL(generated);
    assert.equal(parsed.pathname, mount);
    assert.equal(parsed.search, '');
    assert.ok(parsed.hash.length < oversized.length, 'the rejected hash must not contaminate the new link');
    assert.equal((await readShareURL(generated)).source, draftSource);
    assert.equal(await rejected.evaluate(() => navigator.clipboard.readText()), generated);
    await rejected.close();
  });

  await measure('editing hides the old share address until an explicit new Share', async () => {
    const editing = await open(primary, sharedURL);
    await sourceEquals(editing, sharedSource);
    await editing.locator('#share').click();
    await editing.locator('#share-message').filter({ hasText: /copied/i }).waitFor();
    const oldLink = await editing.locator('#share-url').inputValue();
    assert.equal((await readShareURL(oldLink)).source, sharedSource);
    const edited = 'print("Only the new version belongs in the next link. 🌙")\n';
    await editing.locator('#source').fill(edited);
    await editing.locator('#share-url').waitFor({ state: 'hidden' });
    assert.equal(await editing.locator('#share-url').inputValue(), '');
    await editing.locator('#share-message').filter({ hasText: /Share code.*this version|Share code again|program changed/i }).waitFor();
    await editing.evaluate(() => new Promise(resolve => setTimeout(resolve, 850)));
    assert.equal(await editing.locator('#share-url').isVisible(), false, 'an edit must not silently regenerate the share address');
    assert.equal(await editing.locator('#share-url').inputValue(), '');
    await editing.locator('#share').click();
    await editing.locator('#share-url').waitFor({ state: 'visible' });
    await editing.locator('#share-message').filter({ hasText: /copied/i }).waitFor();
    const newLink = await editing.locator('#share-url').inputValue();
    assert.notEqual(newLink, oldLink);
    assert.equal((await readShareURL(newLink)).source, edited);
    assert.equal((await readShareURL(oldLink)).source, sharedSource, 'existing links remain durable snapshots');
    assert.equal(await editing.evaluate(() => navigator.clipboard.readText()), newLink);
    await editing.close();
  });

  await measure('invalid hashchange leaves current source intact', async () => {
    const before = await page.locator('#source').inputValue();
    await page.evaluate(() => { location.hash = '#minyar=v1.u.1.e8b7be43.YR'; });
    await page.locator('#share-message').filter({ hasText: /damaged|incomplete|new link/i }).waitFor();
    await sourceEquals(page, before);
    await noAutomaticWork(page);
  });

  await measure('only an explicit Run executes shared source', async () => {
    const code = 'print("Shared code ran. 🌙")\n';
    await page.evaluate(hash => { location.hash = hash; }, await encodeShareFragment(code));
    await sourceEquals(page, code);
    await noAutomaticWork(page);
    await page.locator('#run').click();
    await page.waitForFunction(() => document.getElementById('output').textContent === 'Shared code ran. 🌙\n'
      && !document.getElementById('run').disabled, undefined, { timeout: 135_000 });
    assert.ok((await page.evaluate(() => window.__sharingRequests)).some(request => request.type === 'run'));
  });
  await primary.close();

  await measure('an unchanged shared link preserves the local draft through pagehide and reload', async () => {
    const context = await contextFor('unchanged-shared-draft', { seedOnce: true });
    const viewed = await open(context, sharedURL);
    await sourceEquals(viewed, sharedSource);
    await noAutomaticWork(viewed);
    const stored = () => viewed.evaluate(() => JSON.parse(localStorage.getItem('minyar.playground.draft.v1')));
    assert.deepEqual(await stored(), { version: 1, exampleId: 'hello', source: draftSource });
    await viewed.reload({ waitUntil: 'load' });
    await sourceEquals(viewed, sharedSource);
    await noAutomaticWork(viewed);
    assert.deepEqual(await stored(), { version: 1, exampleId: 'hello', source: draftSource },
      'reload must not mask a pagehide overwrite by reseeding storage');
    await viewed.goto(baseURL, { waitUntil: 'load' });
    await sourceEquals(viewed, draftSource);
    assert.equal(await viewed.locator('#example-title').textContent(), tour[0].title);
    assert.deepEqual(await stored(), { version: 1, exampleId: 'hello', source: draftSource });
    await noAutomaticWork(viewed);
    await context.close();
  });

  await measure('editing shared code clears the old hash and reloads the edited draft and title', async () => {
    const context = await contextFor('edited-shared-draft', { seedOnce: true });
    const editing = await open(context, sharedURL);
    await sourceEquals(editing, sharedSource);
    const title = await editing.locator('#example-title').textContent();
    const historyLength = await editing.evaluate(() => {
      window.__editingHashChanges = 0;
      window.addEventListener('hashchange', () => window.__editingHashChanges++);
      return history.length;
    });
    const edited = 'print("My edited shared program survives reload. 🌙")\n';
    await editing.locator('#source').fill(edited);
    await editing.waitForFunction(expected => JSON.parse(localStorage.getItem('minyar.playground.draft.v1'))?.source === expected
      && document.getElementById('draft-state').textContent === 'Saved on this device', edited);
    assert.equal(new URL(editing.url()).hash, '');
    assert.equal(await editing.evaluate(() => window.__editingHashChanges), 0, 'clearing a stale shared hash must not navigate');
    assert.equal(await editing.evaluate(() => history.length), historyLength, 'editing must replace the history entry');
    await editing.reload({ waitUntil: 'load' });
    await sourceEquals(editing, edited);
    assert.equal(await editing.locator('#example-title').textContent(), title);
    assert.equal(new URL(editing.url()).hash, '');
    assert.equal(await editing.evaluate(() => JSON.parse(localStorage.getItem('minyar.playground.draft.v1')).source), edited);
    await noAutomaticWork(editing);
    await context.close();
  });

  await measure('delayed clipboard writes stay ordered across an edit and a second Share', async () => {
    const context = await contextFor('serialized-clipboard');
    await context.addInitScript(() => {
      if (!navigator.clipboard) return;
      window.__clipboardWrites = [];
      window.__clipboardCompletions = [];
      window.__controlledClipboard = '';
      Object.defineProperty(navigator.clipboard, 'writeText', { configurable: true, value(text) {
        return new Promise(resolve => {
          const index = window.__clipboardWrites.length;
          window.__clipboardWrites.push({ text, finish() {
            window.__controlledClipboard = text;
            window.__clipboardCompletions.push(index);
            resolve();
          } });
        });
      } });
      window.__releaseClipboardWrite = index => window.__clipboardWrites[index].finish();
    });
    const copying = await open(context, sharedURL);
    await sourceEquals(copying, sharedSource);
    await copying.locator('#share').click();
    await copying.waitForFunction(() => window.__clipboardWrites.length === 1);
    const firstLink = await copying.locator('#share-url').inputValue();
    assert.equal((await readShareURL(firstLink)).source, sharedSource);
    assert.equal(await copying.locator('#share').isEnabled(), true, 'a pending clipboard prompt must leave Share usable');
    const edited = 'print("The second Share is the latest snapshot.")\n';
    await copying.locator('#source').fill(edited);
    await copying.locator('#share-url').waitFor({ state: 'hidden' });
    await copying.locator('#share').click();
    await copying.locator('#share-url').waitFor({ state: 'visible' });
    const secondLink = await copying.locator('#share-url').inputValue();
    assert.notEqual(secondLink, firstLink);
    assert.equal((await readShareURL(secondLink)).source, edited);
    await settledFrames(copying);
    assert.equal(await copying.evaluate(() => window.__clipboardWrites.length), 1,
      'the second native clipboard write must wait for the first write to finish');
    assert.equal(await copying.locator('#share').isEnabled(), true);
    await copying.evaluate(() => window.__releaseClipboardWrite(0));
    await copying.waitForFunction(() => window.__clipboardWrites.length === 2);
    assert.doesNotMatch(await copying.locator('#share-message').textContent(), /copied/i,
      'completion of an older write must not report the newer link as copied');
    assert.equal(await copying.locator('#share-url').inputValue(), secondLink);
    await copying.evaluate(() => window.__releaseClipboardWrite(1));
    await copying.locator('#share-message').filter({ hasText: /copied/i }).waitFor();
    assert.equal(await copying.evaluate(() => window.__controlledClipboard), secondLink);
    assert.deepEqual(await copying.evaluate(() => window.__clipboardWrites.map(entry => entry.text)), [firstLink, secondLink]);
    assert.deepEqual(await copying.evaluate(() => window.__clipboardCompletions), [0, 1]);
    await context.close();
  });

  // Keep the real codec, but delay its asynchronous result to exercise edits
  // and hash navigation occurring while the UI is awaiting a decoder.
  const delayed = await contextFor('delayed-decode');
  await delayed.route(url => url.pathname.endsWith('/share.mjs') && !url.searchParams.has('original'), route => route.fulfill({
    contentType: 'application/javascript', body: `
export * from './share.mjs?original=1';
import { readShareURL as readOriginal, decodeShareFragment as decodeOriginal } from './share.mjs?original=1';
async function delay(result) {
  if (result?.source.includes('HOLD_SHARED_DECODE')) {
    globalThis.__sharingDecodeHeld = true;
    await new Promise(resolve => { globalThis.__releaseSharingDecode = resolve; });
    globalThis.__sharingDecodeHeld = false;
  }
  return result;
}
export async function readShareURL(value) { return delay(await readOriginal(value)); }
export async function decodeShareFragment(value) { return delay(await decodeOriginal(value)); }
`,
  }));
  const racing = await open(delayed);
  const held = await encodeShareFragment('print("HOLD_SHARED_DECODE")\n');

  await measure('an edit made during shared-source decoding is preserved', async () => {
    await racing.evaluate(hash => { location.hash = hash; }, held);
    await racing.waitForFunction(() => window.__sharingDecodeHeld === true);
    const edited = 'print("My newer edit stays here.")\n';
    await racing.locator('#source').fill(edited);
    await racing.evaluate(() => window.__releaseSharingDecode());
    await racing.waitForFunction(() => window.__sharingDecodeHeld === false);
    await settledFrames(racing);
    await sourceEquals(racing, edited);
  });

  await measure('a newer hash wins over an earlier delayed decode', async () => {
    await racing.evaluate(() => { location.hash = '#neutral'; });
    await settledFrames(racing);
    await racing.evaluate(hash => { location.hash = hash; }, held);
    await racing.waitForFunction(() => window.__sharingDecodeHeld === true);
    const newest = 'print("The newest link wins.")\n';
    await racing.evaluate(hash => { location.hash = hash; }, await encodeShareFragment(newest));
    await sourceEquals(racing, newest);
    await racing.evaluate(() => window.__releaseSharingDecode());
    await racing.waitForFunction(() => window.__sharingDecodeHeld === false);
    await settledFrames(racing);
    await sourceEquals(racing, newest);
  });
  await delayed.close();

  assert.deepEqual(externalRequests, [], 'all resources must stay on the static playground origin');
  assert.deepEqual(failures, [], 'the nested static site must serve every requested asset');
  assert.deepEqual(pageErrors, [], 'sharing flows must not produce uncaught page errors');
  const payload = new URLSearchParams(new URL(sharedURL).hash.slice(1)).get('minyar').split('.').at(-1);
  assert.ok(requests.every(url => !url.includes(privateMarker) && !url.includes('minyar=') && !url.includes(payload)), 'source fragments must never enter HTTP request URLs');
  report.passed = true;
  console.log(`PASS ${checks.length} independent Chromium sharing flows`);
} catch (error) {
  report.passed = false;
  report.error = { message: error.message, stack: error.stack };
  if (currentPage && !currentPage.isClosed()) {
    await currentPage.screenshot({ path: path.join(evidence, 'sharing-browser-failure.png'), fullPage: true }).catch(() => {});
    report.failureState = await currentPage.evaluate(() => ({
      sourceBytes: new TextEncoder().encode(document.getElementById('source')?.value ?? '').length,
      message: document.getElementById('share-message')?.textContent,
      status: document.getElementById('status')?.textContent,
      requests: window.__sharingRequests.map(({ id, type }) => ({ id, type })),
    })).catch(() => null);
  }
  throw error;
} finally {
  report.finishedAt = new Date().toISOString();
  report.requests = requests;
  report.externalRequests = externalRequests;
  report.pageErrors = pageErrors;
  report.httpErrors = failures;
  await writeFile(path.join(evidence, 'sharing-browser.json'), JSON.stringify(report, null, 2) + '\n');
  await browser?.close();
  server.closeAllConnections();
  await new Promise((resolve, reject) => server.close(error => error ? reject(error) : resolve()));
}
