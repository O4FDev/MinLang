import assert from 'node:assert/strict';
import { createReadStream } from 'node:fs';
import { mkdir, readFile, stat, writeFile } from 'node:fs/promises';
import { createServer } from 'node:http';
import path from 'node:path';
import { performance } from 'node:perf_hooks';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { tour } from '../playground/tour.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));
const site = path.resolve(root, process.env.MINYAR_PLAYGROUND_DIR ?? 'build/playground');
const evidence = path.resolve(root, process.env.MINYAR_WASM_EVIDENCE ?? 'build/wasm-evidence');
const dependency = path.join(root, 'build/playground-tests/node_modules/playwright/index.mjs');
const { chromium } = await import(pathToFileURL(dependency).href);
const packageInfo = JSON.parse(await readFile(path.join(path.dirname(dependency), 'package.json'), 'utf8'));
const expectedVersion = JSON.parse(await readFile(new URL('../playground/test-package.json', import.meta.url), 'utf8')).devDependencies.playwright;
assert.equal(packageInfo.version, expectedVersion, 'browser checks must use the pinned Playwright version');
await stat(path.join(site, 'index.html'));
await mkdir(evidence, { recursive: true });

const COLD_TIMEOUT = 135_000;
const checks = [];
const externalRequests = [];
const consoleErrors = [];
const pageErrors = [];
const httpErrors = [];
const assetRequests = new Map();
const report = { startedAt: new Date().toISOString(), playwright: packageInfo.version, checks };
const mimeTypes = {
  '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8', '.mjs': 'application/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8', '.wasm': 'application/wasm',
  '.svg': 'image/svg+xml', '.png': 'image/png', '.map': 'application/json',
};

const server = createServer(async (request, response) => {
  try {
    if (request.method !== 'GET' && request.method !== 'HEAD') {
      response.writeHead(405).end();
      return;
    }
    const url = new URL(request.url, 'http://localhost');
    const pathname = decodeURIComponent(url.pathname === '/' ? '/index.html' : url.pathname);
    const filename = path.resolve(site, `.${pathname}`);
    if (!filename.startsWith(`${site}${path.sep}`)) {
      response.writeHead(403).end();
      return;
    }
    const info = await stat(filename);
    if (!info.isFile()) throw new Error('Not a file');
    assetRequests.set(pathname, (assetRequests.get(pathname) ?? 0) + 1);
    response.setHeader('Content-Type', mimeTypes[path.extname(filename)] ?? 'application/octet-stream');
    response.setHeader('Cache-Control', filename.endsWith('.html') ? 'no-store' : 'public, max-age=300');
    if (filename.endsWith('index.html') && url.searchParams.has('execution-timeout')) {
      const timeout = Number(url.searchParams.get('execution-timeout'));
      assert.ok(Number.isInteger(timeout) && timeout >= 100 && timeout <= 120_000);
      const html = (await readFile(filename, 'utf8')).replace(/data-run-timeout-ms="\d+"/, `data-run-timeout-ms="${timeout}"`);
      response.setHeader('Content-Length', Buffer.byteLength(html));
      response.writeHead(200);
      response.end(request.method === 'HEAD' ? undefined : html);
      return;
    }
    response.setHeader('Content-Length', info.size);
    response.writeHead(200);
    if (request.method === 'HEAD') response.end();
    else createReadStream(filename).on('error', (error) => response.destroy(error)).pipe(response);
  } catch (error) {
    httpErrors.push({ url: request.url, message: error.message });
    if (!response.headersSent) response.writeHead(404);
    response.end('Not found');
  }
});
await new Promise((resolve, reject) => {
  server.once('error', reject);
  server.listen(0, '127.0.0.1', resolve);
});
const origin = `http://127.0.0.1:${server.address().port}`;
let browser;
let currentPage;

// Observe the real worker protocol without replacing its implementation.
function observeWorkers() {
  const NativeWorker = window.Worker;
  window.__minyarTestTrace = [];
  window.__minyarTestWorkers = [];
  window.Worker = class extends NativeWorker {
    constructor(...args) {
      super(...args);
      this.testIndex = window.__minyarTestWorkers.length;
      window.__minyarTestWorkers.push(this);
      this.addEventListener('message', ({ data }) => {
        window.__minyarTestTrace.push({ kind: 'reply', worker: this.testIndex, id: data?.id,
          type: data?.type, phase: data?.phase, message: data?.message, at: performance.now() });
      });
    }
    postMessage(...args) {
      window.__minyarTestTrace.push({ kind: 'request', worker: this.testIndex,
        id: args[0]?.id, type: args[0]?.type, at: performance.now() });
      return super.postMessage(...args);
    }
    terminate() {
      window.__minyarTestTrace.push({ kind: 'terminated', worker: this.testIndex, at: performance.now() });
      return super.terminate();
    }
  };
}

async function contextFor(name, options = {}) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1100 }, acceptDownloads: true, ...options });
  await context.addInitScript(observeWorkers);
  context.on('request', (request) => {
    const url = new URL(request.url());
    if (['http:', 'https:'].includes(url.protocol) && url.origin !== origin) externalRequests.push({ context: name, url: request.url() });
  });
  context.on('page', (page) => {
    page.setDefaultTimeout(15_000);
    page.on('pageerror', (error) => pageErrors.push({ context: name, message: error.message }));
    page.on('console', (message) => {
      if (message.type() === 'error') consoleErrors.push({ context: name, message: message.text() });
    });
  });
  return context;
}

async function openPage(context, suffix = '/') {
  const page = await context.newPage();
  currentPage = page;
  const response = await page.goto(`${origin}${suffix}`, { waitUntil: 'load' });
  assert.equal(response.status(), 200);
  await page.locator('.tour-button').last().waitFor();
  return page;
}

async function outputEquals(page, expected, timeout = COLD_TIMEOUT) {
  await page.waitForFunction((value) => document.getElementById('output').textContent === value
    && !document.getElementById('run').disabled && document.getElementById('stop').disabled,
  expected, { timeout });
  assert.equal(await page.locator('#output').textContent(), expected);
}

async function runSource(page, code, expected, shortcut) {
  await page.locator('#source').fill(code);
  if (shortcut) await page.locator('#source').press(shortcut);
  else await page.getByRole('button', { name: 'Run code' }).click();
  await outputEquals(page, expected);
}

async function runningRequest(page) {
  const request = await page.evaluate(() => [...window.__minyarTestTrace].reverse().find((entry) => entry.kind === 'request' && entry.type === 'run'));
  assert.ok(request, 'Run must send a worker request');
  await page.waitForFunction(({ id, worker }) => window.__minyarTestTrace.some((entry) => entry.kind === 'reply'
    && entry.id === id && entry.worker === worker && entry.phase === 'running'), request, { timeout: COLD_TIMEOUT });
  return request;
}

async function measure(name, operation) {
  const start = performance.now();
  await operation();
  const result = { name, elapsedMs: Math.round(performance.now() - start) };
  if (currentPage && !currentPage.isClosed()) {
    result.timing = await currentPage.locator('#timing').textContent();
    result.status = await currentPage.locator('#status').textContent();
  }
  checks.push(result);
  console.log(`playground: ${name} (${result.elapsedMs} ms)`);
}

// Independent scalar-coordinate walk checks the textarea's UTF-16 selection.
function utf16Offset(source, row, column) {
  let line = 1;
  let position = 1;
  let offset = 0;
  for (const character of source) {
    if (line === row && position === column) return offset;
    offset += character.length;
    if (character === '\n') { line += 1; position = 1; }
    else position += 1;
  }
  return offset;
}

try {
  browser = await chromium.launch({ headless: true, timeout: 30_000, args: ['--no-sandbox'] });
  report.browser = browser.version();
  const desktop = await contextFor('real');
  const page = await openPage(desktop);

  await measure('cold compiler runs the hello tour', async () => {
    assert.equal(await page.locator('#source').inputValue(), tour[0].source);
    await page.getByRole('button', { name: 'Run code' }).click();
    await outputEquals(page, tour[0].expected);
    assert.ok((await page.evaluate(() => window.__minyarTestTrace)).some((entry) => entry.phase === 'running'), 'real worker must report execution phase');
    await page.screenshot({ path: path.join(evidence, 'desktop.png'), fullPage: true });
  });

  await measure('download contains a real WebAssembly module', async () => {
    const [download] = await Promise.all([
      page.waitForEvent('download'),
      page.getByRole('button', { name: 'Save .wasm' }).click(),
    ]);
    assert.equal(download.suggestedFilename(), 'main.wasm');
    const saved = path.join(evidence, 'hello.wasm');
    await download.saveAs(saved);
    const bytes = await readFile(saved);
    assert.deepEqual([...bytes.subarray(0, 8)], [0, 97, 115, 109, 1, 0, 0, 0]);
    assert.ok(bytes.length > 8, 'download must contain the compiled program');
  });

  await measure('tour selection changes and runs the program', async () => {
    await page.getByRole('button', { name: tour[1].title, exact: true }).click();
    assert.equal(await page.locator('#example-title').textContent(), tour[1].title);
    assert.equal(await page.locator('#source').inputValue(), tour[1].source);
    assert.equal(await page.getByRole('button', { name: tour[1].title, exact: true }).getAttribute('aria-current'), 'step');
    await page.getByRole('button', { name: 'Run code' }).click();
    await outputEquals(page, tour[1].expected);
  });

  await measure('reset restores the tour and editor keyboard focus can escape', async () => {
    await page.locator('#source').fill('// A draft\n');
    await page.locator('#source').press('Tab');
    assert.ok((await page.locator('#source').inputValue()).endsWith('    '));
    await page.locator('#source').press('Shift+Tab');
    assert.equal(await page.locator('#source').evaluate((element) => document.activeElement === element), false);
    await page.getByRole('button', { name: 'Reset example' }).click();
    assert.equal(await page.locator('#source').inputValue(), tour[1].source);
    assert.equal(await page.locator('#source').evaluate((element) => document.activeElement === element), true);
  });

  await measure('live type diagnostic selects the right Unicode location', async () => {
    const broken = 'let greeting = "🚀"; let lights: Integer = "three"\nprint(lights)\n';
    await page.locator('#source').fill(broken);
    const location = page.getByRole('button', { name: /^Go to line 1, column / }).first();
    await location.waitFor({ timeout: COLD_TIMEOUT });
    const match = /:(\d+):(\d+)$/.exec(await location.textContent());
    assert.ok(match, 'diagnostic must carry file, line and column');
    const [, rowText, columnText] = match;
    const row = Number(rowText);
    const column = Number(columnText);
    const expected = utf16Offset(broken, row, column);
    assert.ok(expected > column - 1, 'the diagnostic must follow the astral character');
    await location.click();
    const selection = await page.locator('#source').evaluate((element) => ({
      start: element.selectionStart, end: element.selectionEnd, focused: document.activeElement === element,
    }));
    assert.equal(selection.start, expected);
    assert.ok(selection.end >= selection.start);
    assert.equal(selection.focused, true);
    assert.match(await page.locator('#diagnostics').textContent(), /Integer|Text/);
  });

  await measure('fix and run with Control Enter and Meta Enter', async () => {
    await runSource(page, 'print("The harbour is ready. 🚀")\n', 'The harbour is ready. 🚀\n', 'Control+Enter');
    await runSource(page, 'print("A second thought.")\n', 'A second thought.\n', 'Meta+Enter');
    assert.equal(await page.locator('#diagnostic-count').textContent(), 'All clear');
  });

  await measure('draft survives reload', async () => {
    const draft = await page.locator('#source').inputValue();
    await page.waitForFunction((expected) => {
      const saved = JSON.parse(localStorage.getItem('minyar.playground.draft.v1'));
      return saved?.source === expected;
    }, draft);
    await page.reload({ waitUntil: 'load' });
    await page.locator('.tour-button').last().waitFor();
    assert.equal(await page.locator('#source').inputValue(), draft);
    assert.equal(await page.locator('#example-title').textContent(), tour[1].title);
    assert.match(await page.locator('#status').textContent(), /saved draft/);
  });

  await measure('Stop ends an infinite program and a fresh worker runs again', async () => {
    await page.locator('#source').fill('while true { }\n');
    await page.getByRole('button', { name: 'Run code' }).click();
    const request = await runningRequest(page);
    await page.getByRole('button', { name: 'Stop', exact: true }).click();
    assert.match(await page.locator('#status').textContent(), /^Stopped/);
    assert.equal(await page.getByRole('button', { name: 'Stop', exact: true }).isDisabled(), true);
    assert.ok((await page.evaluate(() => window.__minyarTestTrace)).some((entry) => entry.kind === 'terminated' && entry.worker === request.worker));
    await runSource(page, 'print("Back again.")\n', 'Back again.\n');
    assert.ok(await page.evaluate(() => window.__minyarTestWorkers.length >= 2));
  });

  await measure('390 pixel layout remains usable without page overflow', async () => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.getByRole('button', { name: tour[2].title, exact: true }).click();
    await page.getByRole('button', { name: 'Run code' }).click();
    await outputEquals(page, tour[2].expected);
    const sizes = await page.evaluate(() => ({
      width: document.documentElement.clientWidth,
      document: document.documentElement.scrollWidth,
      body: document.body.scrollWidth,
    }));
    assert.equal(sizes.width, 390);
    assert.ok(sizes.document <= sizes.width && sizes.body <= sizes.width, JSON.stringify(sizes));
    await page.screenshot({ path: path.join(evidence, 'mobile.png'), fullPage: true });
  });
  await desktop.close();

  const limited = await contextFor('execution-timeout');
  const timed = await openPage(limited, '/?execution-timeout=250');
  await measure('execution timeout starts at running phase and recovers', async () => {
    await timed.locator('#source').fill(tour[0].source + '\n');
    await timed.locator('#status').filter({ hasText: 'No errors found. Ready to run.' }).waitFor({ timeout: COLD_TIMEOUT });
    await timed.getByRole('button', { name: 'Run code' }).click();
    await outputEquals(timed, tour[0].expected);
    await timed.locator('#source').fill('while true { }\n');
    await timed.getByRole('button', { name: 'Run code' }).click();
    const request = await runningRequest(timed);
    await timed.locator('.diagnostic-help').filter({ hasText: 'The program exceeded 250 ms' }).waitFor();
    assert.equal(await timed.getByRole('button', { name: 'Run code' }).isEnabled(), true);
    const trace = await timed.evaluate(() => window.__minyarTestTrace);
    const running = trace.find((entry) => entry.kind === 'reply' && entry.id === request.id && entry.worker === request.worker && entry.phase === 'running');
    const terminated = trace.find((entry) => entry.kind === 'terminated' && entry.worker === request.worker && entry.at >= running.at);
    assert.ok(terminated, 'execution limit must terminate the worker');
    const elapsed = terminated.at - running.at;
    assert.ok(elapsed >= 200 && elapsed < 5000, `250 ms execution limit took ${elapsed} ms`);
    report.executionTimeoutMs = Math.round(elapsed);
    await runSource(timed, 'print("After the timeout.")\n', 'After the timeout.\n');
  });
  await limited.close();

  const hostile = '<img src="/should-not-load" onerror="globalThis.__minyarXss=true">\n<script>globalThis.__minyarXss=true</script>';
  const controlledWorker = `
const hostile = ${JSON.stringify(hostile)};
let held;
function reply(request, stale = false) {
  const diagnostics = stale ? [{ message: 'STALE_DIAGNOSTIC_SHOULD_NOT_APPEAR', line: 1, column: 1 }]
    : request.source.includes('DIAGNOSTIC_PAYLOAD') ? [{ message: hostile, file: 'input.min', line: 1, column: 1, sourceLine: hostile, label: hostile, help: [hostile, 'Every compiler suggestion should be visible.'] }] : [];
  self.postMessage({ id: request.id, type: 'result', diagnostics,
    output: request.type === 'run' ? (stale ? 'STALE_OUTPUT_SHOULD_NOT_APPEAR' : hostile) : '',
    exitCode: diagnostics.length ? 1 : 0, compileMs: 1, runMs: 1,
    wasm: new Uint8Array([0, 97, 115, 109, 1, 0, 0, 0]) });
}
self.onmessage = ({ data }) => {
  if (data.control === 'release') { reply(held, true); held = null; return; }
  if (data.control === 'release-error') {
    self.postMessage({ id: held.id, type: 'error', message: 'STALE_ERROR_SHOULD_NOT_APPEAR' });
    held = null;
    return;
  }
  if (data.source.includes('HOLD_OLD')) {
    held = data;
    self.postMessage({ id: data.id, type: 'progress', phase: 'checking', message: 'Holding old request' });
    return;
  }
  if (data.source.includes('HOLD_RUNNING')) {
    held = data;
    self.postMessage({ id: data.id, type: 'progress', phase: 'running', message: 'Running your program…' });
    return;
  }
  if (data.type === 'run') self.postMessage({ id: data.id, type: 'progress', phase: 'running', message: 'Running your program…' });
  reply(data);
};`;
  const controlled = await contextFor('controlled-protocol');
  await controlled.route('**/worker.mjs', (route) => route.fulfill({ contentType: 'application/javascript', body: controlledWorker }));
  const adversarial = await openPage(controlled, '/?execution-timeout=250');

  await measure('late results cannot overwrite the latest source', async () => {
    await adversarial.evaluate(() => {
      window.__minyarTextHistory = [];
      const output = document.getElementById('output');
      const diagnostics = document.getElementById('diagnostics');
      const observer = new MutationObserver(() => window.__minyarTextHistory.push(output.textContent + diagnostics.textContent));
      for (const element of [output, diagnostics]) observer.observe(element, { subtree: true, childList: true, characterData: true });
    });
    for (const control of ['release', 'release-error']) {
      await adversarial.locator('#source').fill('print("HOLD_OLD")\n');
      await adversarial.getByRole('button', { name: 'Run code' }).click();
      await adversarial.locator('#status').filter({ hasText: 'Holding old request' }).waitFor();
      await adversarial.locator('#source').fill('print("CURRENT")\n');
      await adversarial.locator('#status').filter({ hasText: 'Your latest edit will be checked next' }).waitFor();
      await adversarial.evaluate((value) => window.__minyarTestWorkers.at(-1).postMessage({ control: value }), control);
      await adversarial.locator('#status').filter({ hasText: 'No errors found. Ready to run.' }).waitFor();
    }
    await adversarial.locator('#source').fill('print("HOLD_RUNNING")\n');
    await adversarial.getByRole('button', { name: 'Run code' }).click();
    await runningRequest(adversarial);
    await adversarial.locator('#source').fill('print("CURRENT")\n');
    await adversarial.locator('#status').filter({ hasText: 'No errors found. Ready to run.' }).waitFor();
    const history = await adversarial.evaluate(() => window.__minyarTextHistory);
    assert.ok(history.every((entry) => !entry.includes('STALE_') && !entry.includes('The program exceeded')
      && !entry.includes('The browser compiler could not finish')), 'even a transient stale result, error or timeout must not be rendered');
    assert.equal(await adversarial.locator('#source').inputValue(), 'print("CURRENT")\n');
  });

  await measure('output and compiler excerpts render as text', async () => {
    await adversarial.getByRole('button', { name: 'Run code' }).click();
    await outputEquals(adversarial, hostile);
    assert.equal(await adversarial.locator('#output img, #output script').count(), 0);
    await adversarial.locator('#source').fill('DIAGNOSTIC_PAYLOAD');
    await adversarial.locator('.diagnostic-message').filter({ hasText: hostile }).waitFor();
    assert.equal(await adversarial.locator('.diagnostic-source').textContent(), hostile);
    assert.ok((await adversarial.locator('.diagnostic-help').allTextContents()).includes('Every compiler suggestion should be visible.'));
    assert.equal(await adversarial.locator('#diagnostics img, #diagnostics script').count(), 0);
    assert.equal(await adversarial.evaluate(() => window.__minyarXss === true), false);
  });

  await measure('UTF-8 source limit disables Run', async () => {
    await adversarial.locator('#source').fill('🚀'.repeat(16_385));
    assert.equal(await adversarial.getByRole('button', { name: 'Run code' }).isDisabled(), true);
    assert.match(await adversarial.locator('#status').textContent(), /64 KiB source limit/);
  });
  await controlled.close();

  const unavailableStorage = await contextFor('unavailable-storage');
  await unavailableStorage.addInitScript(() => {
    Object.defineProperty(window, 'localStorage', { get() { throw new DOMException('Storage unavailable', 'SecurityError'); } });
  });
  await unavailableStorage.route('**/worker.mjs', (route) => route.fulfill({ contentType: 'application/javascript', body: controlledWorker }));
  const noStorage = await openPage(unavailableStorage);
  await measure('unavailable local storage keeps the editor usable', async () => {
    await runSource(noStorage, 'print("CURRENT")\n', hostile);
    await noStorage.locator('#draft-state').filter({ hasText: 'Local saving unavailable' }).waitFor();
    assert.equal(await noStorage.getByRole('button', { name: 'Run code' }).isEnabled(), true);
  });
  await unavailableStorage.close();

  assert.deepEqual(externalRequests, [], 'all browser network requests must stay on the static site origin');
  assert.deepEqual(httpErrors, [], 'all requested static assets must exist');
  assert.deepEqual(pageErrors, [], 'the page must have no uncaught errors');
  assert.deepEqual(consoleErrors, [], 'the page must have no console errors');
  report.passed = true;
  console.log(`playground: ${checks.length} browser checks passed`);
} catch (error) {
  report.passed = false;
  report.error = { message: error.message, stack: error.stack };
  if (currentPage && !currentPage.isClosed()) {
    await currentPage.screenshot({ path: path.join(evidence, 'failure.png'), fullPage: true }).catch(() => {});
    report.failureState = await currentPage.evaluate(() => ({
      status: document.getElementById('status')?.textContent,
      diagnostics: document.getElementById('diagnostics')?.textContent,
      output: document.getElementById('output')?.textContent,
      trace: window.__minyarTestTrace,
    })).catch(() => null);
  }
  throw error;
} finally {
  report.finishedAt = new Date().toISOString();
  report.externalRequests = externalRequests;
  report.consoleErrors = consoleErrors;
  report.pageErrors = pageErrors;
  report.httpErrors = httpErrors;
  report.assetRequests = Object.fromEntries(assetRequests);
  await writeFile(path.join(evidence, 'browser.json'), JSON.stringify(report, null, 2) + '\n');
  await browser?.close();
  server.closeAllConnections();
  await new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
}
