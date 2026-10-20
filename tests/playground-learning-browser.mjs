import assert from 'node:assert/strict';
import { createReadStream } from 'node:fs';
import { mkdir, readFile, stat, writeFile } from 'node:fs/promises';
import { createServer } from 'node:http';
import path from 'node:path';
import { performance } from 'node:perf_hooks';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { tour } from '../playground/tour.mjs';
import { guides } from '../playground/tour-guide.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));
const site = path.resolve(root, process.env.MINYAR_PLAYGROUND_DIR ?? 'build/playground');
const evidence = path.resolve(root, process.env.MINYAR_WASM_EVIDENCE ?? 'build/wasm-evidence');
const dependency = path.join(root, 'build/playground-tests/node_modules/playwright/index.mjs');
const { chromium } = await import(pathToFileURL(dependency).href);
const installed = JSON.parse(await readFile(path.join(path.dirname(dependency), 'package.json'), 'utf8'));
const pinned = JSON.parse(await readFile(new URL('../playground/test-package.json', import.meta.url), 'utf8')).devDependencies.playwright;
assert.equal(installed.version, pinned);
const catalog = JSON.parse(await readFile(path.join(site, 'language-examples.json'), 'utf8'));
const entries = catalog.examples;
const contextual = entries.filter((example) => !example.runnable);
await mkdir(evidence, { recursive: true });
const failures = { page: [], console: [], network: [], http: [] };
const report = { startedAt: new Date().toISOString(), playwright: installed.version, document: catalog.document, checks: [] };
const COLD_TIMEOUT = 135_000;
const mime = { '.html': 'text/html; charset=utf-8', '.mjs': 'application/javascript', '.js': 'application/javascript',
  '.css': 'text/css', '.json': 'application/json', '.wasm': 'application/wasm', '.svg': 'image/svg+xml', '.png': 'image/png' };
const server = createServer(async (request, response) => {
  try {
    const url = new URL(request.url, 'http://localhost');
    const filename = path.resolve(site, '.' + decodeURIComponent(url.pathname === '/' ? '/index.html' : url.pathname));
    assert.ok(filename.startsWith(site + path.sep));
    const metadata = await stat(filename);
    assert.ok(metadata.isFile());
    response.writeHead(200, { 'Content-Type': mime[path.extname(filename)] ?? 'application/octet-stream',
      'Content-Length': metadata.size, 'Cache-Control': filename.endsWith('.html') ? 'no-store' : 'public, max-age=300' });
    if (request.method === 'HEAD') response.end();
    else createReadStream(filename).on('error', (error) => response.destroy(error)).pipe(response);
  } catch (error) {
    failures.http.push({ url: request.url, message: error.message });
    if (!response.headersSent) response.writeHead(404);
    response.end('Not found');
  }
});
await new Promise((resolve, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolve); });
const origin = `http://127.0.0.1:${server.address().port}`;
let browser;
let page;

function replaceOnce(source, before, after) {
  assert.equal(source.split(before).length, 2, `challenge edit must replace exactly one ${JSON.stringify(before)}`);
  return source.replace(before, after);
}

// These edits follow the instructions; expected stdout is an independent goal.
const challengeEdits = {
  hello: (source) => replaceOnce(source, '"Ada"', '"Grace"'),
  functions: (source) => replaceOnce(source, 'double(21)', 'double(42)'),
  lists: (source) => replaceOnce(source, '"blue"]', '"blue", "green"]'),
  records: (source) => replaceOnce(source, 'lights: 42', 'lights: 43'),
  choices: (source) => replaceOnce(source, 'Weather.Rain(3)', 'Weather.Clear'),
  lanterns: (source) => replaceOnce(source, 'place: "The harbour"; light: 3', 'place: "The harbour"; light: 5'),
};

async function outputEquals(expected) {
  await page.waitForFunction((value) => document.getElementById('output').textContent === value
    && !document.getElementById('run').disabled && document.getElementById('stop').disabled,
  expected, { timeout: COLD_TIMEOUT });
  assert.equal(await page.locator('#output').textContent(), expected);
  assert.equal(await page.locator('#diagnostic-count').textContent(), 'All clear');
}

async function run(expected) {
  await page.getByRole('button', { name: 'Run code' }).click();
  await outputEquals(expected);
}

async function progressCount(kind) {
  return page.locator('#tour-progress').evaluate((element, column) => {
    const attribute = element.getAttribute(`data-${column}`);
    if (attribute !== null && /^\d+$/.test(attribute)) return Number(attribute);
    const text = element.textContent;
    const after = new RegExp(`(\\d+)\\s*(?:of|/)\\s*6\\s*${column}`, 'i').exec(text);
    const before = new RegExp(`${column}[^\\d]*(\\d+)`, 'i').exec(text);
    if (after || before) return Number((after ?? before)[1]);
    throw new Error(`Progress needs an observable ${column} count: ${text}`);
  }, kind);
}

async function measure(name, operation) {
  const start = performance.now();
  await operation();
  const row = { name, elapsedMs: Math.round(performance.now() - start) };
  if (page && !page.isClosed()) {
    row.timing = await page.locator('#timing').textContent();
    row.status = await page.locator('#status').textContent();
  }
  report.checks.push(row);
  console.log(`learning playground: ${name} (${row.elapsedMs} ms)`);
}

async function clearFilter() {
  await page.locator('#language-search').fill('');
  await page.waitForFunction((total) => document.querySelectorAll('#language-list button[data-example-id]').length === total,
    entries.length);
}

async function chooseDocument(example) {
  await clearFilter();
  await page.locator(`#language-list button[data-example-id="${example.id}"]`).click();
  assert.equal(await page.locator('#source').inputValue(), example.source, `${example.id}: load the exact original source`);
  assert.ok((await page.locator('#example-provenance').textContent()).includes(`${example.file}:${example.line}`));
  assert.ok((await page.locator('#example-context').textContent()).includes(example.reason));
}

async function observedContext() {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1100 } });
  context.on('request', (request) => {
    const url = new URL(request.url());
    if (['http:', 'https:'].includes(url.protocol) && url.origin !== origin) failures.network.push(request.url());
  });
  context.on('page', (opened) => {
    opened.setDefaultTimeout(15_000);
    opened.on('pageerror', (error) => failures.page.push(error.message));
    opened.on('console', (message) => { if (message.type() === 'error') failures.console.push(message.text()); });
  });
  return context;
}

async function catalogReady() {
  await page.waitForFunction((total) => !document.getElementById('source').readOnly
    && document.querySelectorAll('#language-list button[data-example-id]').length === total, entries.length);
}

// Intercept a real worker's result before application listeners receive it.
// Compilation/execution still happen in the shipped worker; release dispatches
// that same captured payload after the user has changed the lesson mode.
function holdRealRunResult() {
  const NativeWorker = window.Worker;
  window.__holdNextMinyarRun = false;
  window.Worker = class extends NativeWorker {
    constructor(...args) {
      super(...args);
      this.runIds = new Set();
      super.addEventListener('message', (event) => {
        if (!window.__holdNextMinyarRun || event.data?.type !== 'result' || !this.runIds.has(event.data.id)) return;
        window.__holdNextMinyarRun = false;
        window.__heldMinyarRun = { worker: this, data: event.data };
        event.stopImmediatePropagation();
      });
    }
    postMessage(data, ...rest) {
      if (data?.type === 'run') this.runIds.add(data.id);
      return super.postMessage(data, ...rest);
    }
  };
}

try {
  browser = await chromium.launch({ headless: true, timeout: 30_000, args: ['--no-sandbox'] });
  report.browser = browser.version();
  const context = await observedContext();
  page = await context.newPage();
  const response = await page.goto(origin, { waitUntil: 'load' });
  assert.equal(response.status(), 200);
  await page.locator('.tour-button').last().waitFor();
  await page.locator('#challenge').waitFor();
  await page.waitForFunction((total) => document.querySelectorAll('#language-list button[data-example-id]').length === total,
    entries.length);

  for (const [index, example] of tour.entries()) {
    await measure(`challenge ${index + 1}: ${example.title}`, async () => {
      if (index === 0) await page.getByRole('button', { name: example.title, exact: true }).click();
      else {
        await page.locator('#next-example').click();
        assert.equal(await page.locator('#example-title').textContent(), example.title);
      }
      const original = await page.locator('#source').inputValue();
      assert.equal(original, example.source);
      await page.locator('#challenge').click();
      assert.equal(await page.locator('#source').inputValue(), original, 'starting a challenge must not silently edit the program');
      assert.ok((await page.locator('#lesson-instruction').textContent()).includes(guides[example.id].instruction));
      await page.locator('#lesson-hint').click();
      await page.getByText(guides[example.id].hint, { exact: true }).waitFor({ state: 'visible' });
      assert.equal(await page.locator('#source').inputValue(), original, 'asking for a hint must preserve the source');
      if (index === 0) {
        await run(example.expected);
        assert.equal(await progressCount('challenges'), 0, 'the unchanged example cannot complete its challenge');
      }
      const feedbackBefore = await page.locator('#lesson-feedback').textContent();
      const edited = challengeEdits[example.id](original);
      await page.locator('#source').fill(edited);
      await run(guides[example.id].expected);
      assert.equal(await progressCount('challenges'), index + 1);
      const feedback = await page.locator('#lesson-feedback').textContent();
      assert.ok(feedback.trim().length > 0 && feedback !== feedbackBefore, 'a completed challenge must give observable feedback');
    });
  }

  await measure('challenge progress survives reload', async () => {
    assert.equal(await progressCount('challenges'), tour.length);
    await page.reload({ waitUntil: 'load' });
    await page.locator('.tour-button').last().waitFor();
    assert.equal(await progressCount('challenges'), tour.length);
    await page.screenshot({ path: path.join(evidence, 'learning-desktop.png'), fullPage: true });
  });

  await measure('all guide blocks are listed and searchable', async () => {
    await clearFilter();
    const ids = await page.locator('#language-list button[data-example-id]').evaluateAll((buttons) => buttons.map((button) => button.dataset.exampleId));
    assert.deepEqual([...ids].sort(), entries.map((example) => example.id).sort());
    const target = entries.find((example) => example.sourceSha256.startsWith('03f2906c7af3'));
    assert.ok(target);
    await page.locator('#language-search').fill(target.title.toUpperCase());
    await page.waitForFunction((id) => {
      const buttons = [...document.querySelectorAll('#language-list button[data-example-id]')].filter((button) => button.getClientRects().length);
      return buttons.length === 1 && buttons[0].dataset.exampleId === id;
    }, target.id);
    await page.locator('#language-search').fill('no-example-has-this-title-6021');
    await page.waitForFunction(() => [...document.querySelectorAll('#language-list button[data-example-id]')]
      .every((button) => !button.getClientRects().length));
    await clearFilter();
  });

  await measure('all contextual blocks keep their original source and explain the Run restriction', async () => {
    for (const example of contextual) {
      await chooseDocument(example);
      assert.equal(await page.getByRole('button', { name: 'Run code' }).isDisabled(), true, `${example.id}: original contextual source is not presented as standalone`);
      await page.locator('#source').fill('print("An explicit complete edit.")\n');
      assert.equal(await page.getByRole('button', { name: 'Run code' }).isEnabled(), true, `${example.id}: an explicit user edit unlocks Run`);
    }
  });

  const printing = entries.find((example) => example.sourceSha256.startsWith('770782c176f4'));
  const parallel = entries.find((example) => example.sourceSha256.startsWith('36478a3e9af2'));
  const declaration = entries.find((example) => example.sourceSha256.startsWith('a90d7ae76d0f'));
  for (const example of [printing, parallel, declaration]) assert.ok(example?.runnable);
  for (const example of entries.filter((entry) => entry.runnable)) {
    await measure(`original guide program: ${example.title}`, async () => {
      await chooseDocument(example);
      await run(example.expected);
      assert.equal(await page.locator('#source').inputValue(), example.source, 'Run must not add hidden scaffolding');
      assert.match(await page.locator('#example-provenance').textContent(), /exact original source/);
      if (example.note) assert.ok((await page.locator('#example-context').textContent()).includes(example.note));
    });
  }

  await measure('a method fragment can run after an explicit complete edit', async () => {
    const method = entries.find((example) => example.sourceSha256.startsWith('eaa578f0560f'));
    const account = entries.find((example) => example.sourceSha256.startsWith('a7cdc8bfbe33'));
    assert.ok(method && account);
    await chooseDocument(method);
    assert.equal(await page.getByRole('button', { name: 'Run code' }).isDisabled(), true);
    // The catalog source remains a fragment. This is a visible user edit that
    // supplies its missing declarations, value and an observable print call.
    const edited = `${account.source}\nlet account = open("Ada")\n${method.source}\nprint(balance(account))\n`;
    await page.locator('#source').fill(edited);
    await run('10\n');
    assert.equal(await page.locator('#source').inputValue(), edited);
    assert.equal(method.classification, 'fragment');
  });

  await measure('an edited guide draft retains provenance, catalog selection and title after reload', async () => {
    await chooseDocument(printing);
    const edited = replaceOnce(printing.source, '"Ada"', '"Grace"');
    await page.locator('#source').fill(edited);
    assert.match(await page.locator('#example-provenance').textContent(), /edited/i);
    assert.doesNotMatch(await page.locator('#example-provenance').textContent(), /exact original source/i);
    await page.waitForFunction(({ source, id }) => {
      const draft = JSON.parse(localStorage.getItem('minyar.playground.draft.v1'));
      return draft?.source === source && draft.exampleId === id;
    }, { source: edited, id: printing.id });
    await page.reload({ waitUntil: 'load' });
    await catalogReady();
    assert.equal(await page.locator('#source').inputValue(), edited);
    assert.equal(await page.locator('#example-title').textContent(), printing.title);
    assert.equal(await page.locator(`#language-list button[data-example-id="${printing.id}"]`).getAttribute('aria-current'), 'true');
    const provenance = await page.locator('#example-provenance').textContent();
    assert.ok(provenance.includes(`${printing.file}:${printing.line}`));
    assert.match(provenance, /edited/i);
    await run('Hello, Grace! You have 42 messages.\nThe answer is true, and the star is ★.\n');
  });

  await measure('the language picker works at 390 pixels without page overflow', async () => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.locator('#language-search').fill('Words with values inside');
    await page.locator(`#language-list button[data-example-id="${printing.id}"]`).click();
    await page.getByRole('button', { name: 'Reset example' }).click();
    assert.equal(await page.locator('#source').inputValue(), printing.source);
    await run(printing.expected);
    const size = await page.evaluate(() => ({ width: document.documentElement.clientWidth,
      document: document.documentElement.scrollWidth, body: document.body.scrollWidth }));
    assert.equal(size.width, 390);
    assert.ok(size.document <= size.width && size.body <= size.width, JSON.stringify(size));
    assert.equal(await progressCount('challenges'), tour.length);
    await page.screenshot({ path: path.join(evidence, 'learning-mobile.png'), fullPage: true });
  });

  report.completedChallenges = await progressCount('challenges');
  await context.close();

  await measure('a held real example result cannot complete a newly entered challenge', async () => {
    const heldContext = await observedContext();
    await heldContext.addInitScript(holdRealRunResult);
    page = await heldContext.newPage();
    await page.goto(origin, { waitUntil: 'load' });
    await catalogReady();
    assert.equal(await progressCount('challenges'), 0);
    // This source matches the challenge output, but Run is still in example
    // mode. Attribution must be captured when the request starts.
    await page.locator('#source').fill(challengeEdits.hello(tour[0].source));
    await page.evaluate(() => { window.__holdNextMinyarRun = true; });
    await page.getByRole('button', { name: 'Run code' }).click();
    await page.waitForFunction(() => Boolean(window.__heldMinyarRun), null, { timeout: COLD_TIMEOUT });
    const captured = await page.evaluate(() => ({ output: window.__heldMinyarRun.data.output,
      wasmBytes: window.__heldMinyarRun.data.wasm?.byteLength ?? 0 }));
    assert.equal(captured.output, guides.hello.expected);
    assert.ok(captured.wasmBytes > 8, 'the held payload must be a real compiled worker result');
    await page.locator('#challenge').click();
    const goal = await page.locator('#lesson-goal').textContent();
    const feedback = await page.locator('#lesson-feedback').textContent();
    assert.equal(goal, guides.hello.expected);
    assert.equal(await progressCount('challenges'), 0);
    await page.evaluate(() => {
      const held = window.__heldMinyarRun;
      delete window.__heldMinyarRun;
      held.worker.dispatchEvent(new MessageEvent('message', { data: held.data }));
    });
    await outputEquals(guides.hello.expected);
    assert.equal(await progressCount('challenges'), 0, 'an earlier example-mode run cannot earn challenge credit');
    assert.equal(await page.locator('#lesson-goal').textContent(), goal);
    assert.equal(await page.locator('#lesson-feedback').textContent(), feedback, 'the earlier result cannot replace challenge feedback');
    await heldContext.close();
  });

  await measure('catalog startup keeps the editor readonly until loading finishes', async () => {
    const deferred = await observedContext();
    let release;
    const gate = new Promise((resolve) => { release = resolve; });
    await deferred.route('**/language-examples.json', async (route) => {
      await gate;
      await route.continue();
    });
    page = await deferred.newPage();
    try {
      await Promise.all([
        page.waitForRequest((request) => new URL(request.url()).pathname === '/language-examples.json'),
        page.goto(origin, { waitUntil: 'commit' }),
      ]);
      await page.locator('#source').waitFor();
      assert.equal(await page.locator('#source').evaluate((element) => element.readOnly), true);
      const original = await page.locator('#source').inputValue();
      await page.locator('#source').press('x');
      assert.equal(await page.locator('#source').inputValue(), original, 'typing during catalog loading must not create a draft that startup overwrites');
    } finally {
      release();
    }
    await catalogReady();
    await page.getByRole('button', { name: tour[1].title, exact: true }).click();
    assert.equal(await page.locator('#source').inputValue(), tour[1].source);
    await deferred.close();
  });

  await measure('a malformed catalog leaves the guided tour editable and runnable', async () => {
    const fallback = await observedContext();
    // A successful HTTP response with invalid JSON exercises catalog failure
    // without manufacturing browser resource/console errors.
    await fallback.route('**/language-examples.json', (route) => route.fulfill({
      status: 200, contentType: 'application/json', body: '{"schemaVersion":',
    }));
    page = await fallback.newPage();
    await page.goto(origin, { waitUntil: 'load' });
    await page.locator('#language-unavailable').waitFor({ state: 'visible' });
    await page.waitForFunction(() => !document.getElementById('source').readOnly);
    assert.equal(await page.locator('.tour-button').count(), tour.length);
    assert.equal(await page.locator('#language-list button[data-example-id]').count(), 0);
    await page.getByRole('button', { name: tour[1].title, exact: true }).click();
    assert.equal(await page.locator('#source').inputValue(), tour[1].source);
    await run(tour[1].expected);
    await fallback.close();
  });

  assert.deepEqual(failures, { page: [], console: [], network: [], http: [] });
  report.passed = true;
  console.log(`PASS ${report.checks.length} real learning UI checks; all ${entries.length} guide blocks, ${contextual.length} contextual entries and ${tour.length} challenges`);
} catch (error) {
  report.passed = false;
  report.error = { message: error.message, stack: error.stack };
  if (page && !page.isClosed()) {
    await page.screenshot({ path: path.join(evidence, 'learning-failure.png'), fullPage: true }).catch(() => {});
    report.failureState = await page.evaluate(() => ({
      title: document.getElementById('example-title')?.textContent,
      source: document.getElementById('source')?.value,
      status: document.getElementById('status')?.textContent,
      diagnostics: document.getElementById('diagnostics')?.textContent,
      output: document.getElementById('output')?.textContent,
      instruction: document.getElementById('lesson-instruction')?.textContent,
      feedback: document.getElementById('lesson-feedback')?.textContent,
      progress: document.getElementById('tour-progress')?.outerHTML,
    })).catch(() => null);
  }
  throw error;
} finally {
  report.finishedAt = new Date().toISOString();
  report.failures = failures;
  await writeFile(path.join(evidence, 'learning-browser.json'), JSON.stringify(report, null, 2) + '\n');
  await browser?.close();
  server.closeAllConnections();
  await new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
}
