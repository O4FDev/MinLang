import assert from 'node:assert/strict';
import { createReadStream } from 'node:fs';
import { mkdir, readFile, stat, writeFile } from 'node:fs/promises';
import { createServer } from 'node:http';
import path from 'node:path';
import { performance } from 'node:perf_hooks';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { tour } from '../playground/tour.mjs';

// Run only against a built static site, on the leased remote wasm box. Every
// compilation below uses the shipped Worker and real Chromium WebAssembly.
const root = fileURLToPath(new URL('../', import.meta.url));
const site = path.resolve(root, process.env.MINYAR_PLAYGROUND_DIR ?? 'build/playground');
const evidence = path.resolve(root, process.env.MINYAR_WASM_EVIDENCE ?? 'build/wasm-evidence');
const dependency = path.join(root, 'build/playground-tests/node_modules/playwright/index.mjs');
const { chromium } = await import(pathToFileURL(dependency).href);
const installed = JSON.parse(await readFile(path.join(path.dirname(dependency), 'package.json'), 'utf8'));
const pinned = JSON.parse(await readFile(new URL('../playground/test-package.json', import.meta.url), 'utf8')).devDependencies.playwright;
assert.equal(installed.version, pinned);
for (const filename of ['index.html', 'project.mjs', 'project-editor.mjs', 'project-examples.mjs']) await stat(path.join(site, filename));
const guideCatalog = JSON.parse(await readFile(path.join(site, 'language-examples.json'), 'utf8'));
const namespaceExample = guideCatalog.examples.find(example =>
  example.sourceSha256 === '7934638fcc04b5e75f2eee0a7815c6dc089560f297e0db2862cd38bd0ed0c770');
assert.ok(namespaceExample, 'the exact local module namespace guide excerpt is available');
await mkdir(evidence, { recursive: true });

const DRAFT_KEY = 'minyar.playground.draft.v1';
const COLD_TIMEOUT = 135_000; // App: 120 seconds preparation, then 10 seconds execution.
const mount = '/nested/projects/';
const privateMarker = 'PRIVATE_PROJECT_SOURCE_20261020';
const legacySource = 'print("A private project draft.")\n';
const legacyDraft = { version: 1, exampleId: 'hello', source: legacySource };
const entrySource = `// ${privateMarker}\nuse "./geometry.min" as geometry\nlet point = geometry.Point { x: 20; y: 22 }\nprint(geometry.answer(point))\n`;
const geometry42 = 'public record Point { x: Integer; y: Integer }\npublic function answer(point: Point): Integer { return point.x + point.y }\n';
const geometry43 = geometry42.replace('point.x + point.y', 'point.x + point.y + 1');
const geometry44 = geometry42.replace('point.x + point.y', 'point.x + point.y + 2');
const brokenGeometry = 'public record Point { x: Integer; y: Integer }\npublic function answer(point: Point): Integer { let marker = "🚀"; return "wrong" }\n';
const checks = [];
const failures = { page: [], console: [], network: [], http: [] };
const requests = [];
const report = { startedAt: new Date().toISOString(), playwright: installed.version, checks };
const mime = { '.html': 'text/html; charset=utf-8', '.mjs': 'application/javascript; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8', '.wasm': 'application/wasm', '.svg': 'image/svg+xml' };
const server = createServer(async (request, response) => {
  requests.push(request.url);
  try {
    assert.ok(['GET', 'HEAD'].includes(request.method));
    const address = new URL(request.url, 'http://localhost');
    assert.ok(address.pathname.startsWith(mount), 'asset request escaped the nested static site');
    const filename = path.resolve(site, decodeURIComponent(address.pathname.slice(mount.length) || 'index.html'));
    assert.ok(filename.startsWith(site + path.sep));
    const metadata = await stat(filename);
    assert.ok(metadata.isFile());
    response.writeHead(200, { 'Content-Type': mime[path.extname(filename)] ?? 'application/octet-stream',
      'Content-Length': metadata.size, 'Cache-Control': filename.endsWith('.html') ? 'no-store' : 'public, max-age=300' });
    if (request.method === 'HEAD') response.end();
    else createReadStream(filename).on('error', error => response.destroy(error)).pipe(response);
  } catch (error) {
    failures.http.push({ url: request.url, message: error.message });
    if (!response.headersSent) response.writeHead(404);
    response.end('Not found');
  }
});
await new Promise((resolve, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolve); });
const origin = `http://127.0.0.1:${server.address().port}`;
const baseURL = origin + mount;
let browser, currentPage;

function project(files) {
  return { version: 1, entry: 'main.min', files: Object.entries(files)
    .sort(([left], [right]) => left < right ? -1 : left > right ? 1 : 0)
    .map(([path, source]) => ({ path, source })) };
}

function projectDraft(files, currentPath = 'main.min') {
  return { version: 2, exampleId: 'hello', project: project(files), currentPath };
}

function observeAndSeed({ draft, key }) {
  window.__projectTrace = [];
  window.__projectWorkers = 0;
  const NativeWorker = window.Worker;
  window.Worker = class extends NativeWorker {
    constructor(...args) {
      super(...args);
      this.testWorker = ++window.__projectWorkers;
      window.__projectTrace.push({ kind: 'worker', worker: this.testWorker });
      super.addEventListener('message', event => {
        const { id, type, phase, message, diagnostics, output, exitCode, compileMs, runMs, wasm } = event.data ?? {};
        window.__projectTrace.push({ kind: 'reply', worker: this.testWorker, id, type, phase,
          message, diagnostics, output, exitCode, compileMs, runMs, wasmBytes: wasm?.byteLength });
      });
    }
    postMessage(data, ...rest) {
      window.__projectTrace.push({ kind: 'request', worker: this.testWorker, ...structuredClone(data) });
      return super.postMessage(data, ...rest);
    }
  };
  if (location.protocol === 'http:' && !localStorage.getItem('minyar.test.projects.seeded')) {
    localStorage.setItem(key, JSON.stringify(draft));
    localStorage.setItem('minyar.test.projects.seeded', '1');
  }
}

async function contextFor(name, draft = legacyDraft) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1100 },
    permissions: ['clipboard-read', 'clipboard-write'] });
  await context.addInitScript(observeAndSeed, { draft, key: DRAFT_KEY });
  context.on('request', request => {
    const address = new URL(request.url());
    if (['http:', 'https:'].includes(address.protocol) && address.origin !== origin) failures.network.push({ name, url: request.url() });
  });
  context.on('page', page => {
    page.setDefaultTimeout(15_000);
    page.on('pageerror', error => failures.page.push({ name, message: error.message }));
    page.on('console', message => { if (message.type() === 'error') failures.console.push({ name, message: message.text() }); });
  });
  return context;
}

async function ready(page) {
  await page.waitForFunction(() => !document.getElementById('source')?.readOnly
    && document.querySelector('#project-files button[data-path]')
    && !document.getElementById('project-path').disabled);
  assert.equal(await page.locator('html').getAttribute('data-startup-timeout-ms'), '120000');
  assert.equal(await page.locator('html').getAttribute('data-run-timeout-ms'), '10000');
}

async function open(context, url = baseURL) {
  const page = await context.newPage();
  currentPage = page;
  const response = await page.goto(url, { waitUntil: 'load' });
  assert.equal(response.status(), 200);
  await ready(page);
  return page;
}

async function paths(page) {
  return page.locator('#project-files button[data-path]').evaluateAll(buttons => buttons.map(button => button.dataset.path));
}

async function selectFile(page, filename, { keyboard = false } = {}) {
  // Exact accessible names avoid ambiguous main.min/helper.min prefixes, while
  // normal clicks/Enter still prove the tab is enabled and reachable.
  const target = page.locator('#project-files').getByRole('button', { name: filename, exact: true });
  assert.equal(await target.getAttribute('data-path'), filename);
  if (keyboard) {
    await target.focus();
    await target.press('Enter');
  } else await target.click();
  assert.equal(await page.locator('#source-filename').textContent(), filename);
  assert.equal(await page.locator('#project-files button[aria-current="page"]').getAttribute('data-path'), filename);
  assert.equal(await page.locator('#source').evaluate(element => element === document.activeElement), true,
    `${keyboard ? 'Enter' : 'click'} selects the file and returns focus to the editor`);
}

async function openAdd(page) {
  if (!await page.locator('#project-add-controls').evaluate(element => element.open)) {
    await page.locator('#project-add-controls > summary').click();
  }
}

async function addFile(page, filename, source = '') {
  await openAdd(page);
  await page.locator('#project-path').fill(filename);
  await page.locator('#project-add').click();
  assert.equal(await page.locator('#source-filename').textContent(), filename);
  assert.ok((await paths(page)).includes(filename));
  if (source) await page.locator('#source').fill(source);
}

async function stored(page) {
  return page.evaluate(key => localStorage.getItem(key), DRAFT_KEY);
}

async function waitForDraft(page, expectedProject, currentPath) {
  await page.waitForFunction(({ key, expected, selected }) => {
    const saved = JSON.parse(localStorage.getItem(key));
    return saved?.version === 2 && saved.currentPath === selected && JSON.stringify(saved.project) === JSON.stringify(expected);
  }, { key: DRAFT_KEY, expected: expectedProject, selected: currentPath });
}

async function requestRun(page, shortcut = false) {
  const before = await page.evaluate(() => window.__projectTrace.filter(row => row.kind === 'request' && row.type === 'run').length);
  if (shortcut) await page.locator('#source').press('ControlOrMeta+Enter');
  else await page.locator('#run').click();
  await page.waitForFunction(count => window.__projectTrace.filter(row => row.kind === 'request' && row.type === 'run').length > count,
    before, { timeout: COLD_TIMEOUT });
  const request = await page.evaluate(() => window.__projectTrace.findLast(row => row.kind === 'request' && row.type === 'run'));
  await page.waitForFunction(({ id, worker }) => window.__projectTrace.some(row => row.kind === 'reply'
    && ['result', 'error'].includes(row.type) && row.id === id && row.worker === worker), request, { timeout: COLD_TIMEOUT });
  const result = await page.evaluate(({ id, worker }) => window.__projectTrace.find(row => row.kind === 'reply'
    && ['result', 'error'].includes(row.type) && row.id === id && row.worker === worker), request);
  assert.equal(result.type, 'result', result.message ?? 'the real worker must return a successful result');
  return { request, result };
}

async function run(page, expected, shortcut = false) {
  const { request, result } = await requestRun(page, shortcut);
  assert.deepEqual(result.diagnostics, []);
  assert.equal(result.exitCode, 0);
  assert.equal(result.output, expected, 'stdout has an independent source-level oracle');
  assert.ok(result.wasmBytes > 8, 'Run produces a real WebAssembly executable');
  await page.waitForFunction(value => document.getElementById('output').textContent === value
    && !document.getElementById('run').disabled && document.getElementById('stop').disabled,
  expected, { timeout: COLD_TIMEOUT });
  assert.equal(await page.locator('#diagnostic-count').textContent(), 'All clear');
  return request;
}

async function sharedProjectURL(page, value) {
  const before = await page.evaluate(() => window.__projectTrace.length);
  const fragment = await page.evaluate(async value => {
    const { encodeShareFragment } = await import(new URL('./share.mjs', location.href).href);
    const source = value.files.find(file => file.path === value.entry).source;
    return encodeShareFragment(source, { project: value });
  }, value);
  assert.match(fragment, /^#minyar=v2\.p\./);
  assert.equal(await page.evaluate(() => window.__projectTrace.length), before, 'encoding a link must not start compiler work');
  return baseURL + fragment;
}

async function noAutomaticWork(page) {
  // Advance the page clock across the live-check debounce without sleeping.
  // A delayed check would construct/post to a Worker during this window.
  await page.clock.install();
  await page.clock.fastForward(850);
  assert.equal(await page.evaluate(() => window.__projectWorkers), 0);
  assert.deepEqual(await page.evaluate(() => window.__projectTrace), []);
  assert.equal(await page.locator('#output').textContent(), '');
}

async function measure(name, action) {
  const start = performance.now();
  await action();
  const row = { name, elapsedMs: Math.round(performance.now() - start) };
  if (currentPage && !currentPage.isClosed()) {
    row.timing = await currentPage.locator('#timing').textContent();
    row.status = await currentPage.locator('#status').textContent();
  }
  checks.push(row);
  console.log(`PASS projects-browser/${name}`);
}

try {
  browser = await chromium.launch({ headless: true, timeout: 30_000, args: ['--no-sandbox'] });
  report.browser = browser.version();
  const primary = await contextFor('primary');
  const page = await open(primary);
  let sharedURL;
  let sharedProject;

  await measure('legacy draft restores one entry and retains the source-only worker protocol', async () => {
    assert.deepEqual(await paths(page), ['main.min']);
    assert.equal(await page.locator('#source').inputValue(), legacySource);
    assert.equal(await page.locator('#project-remove').isDisabled(), true);
    assert.match(await page.locator('#project-entry').textContent(), /main\.min/);
    const request = await run(page, 'A private project draft.\n');
    assert.equal(request.source, legacySource);
    assert.equal(Object.hasOwn(request, 'project'), false);
  });

  await measure('an imported public record and function run the entry while its dependency is selected', async () => {
    await page.locator('#source').fill(entrySource);
    await addFile(page, 'geometry.min', geometry42);
    const request = await run(page, '42\n');
    assert.equal(await page.locator('#source-filename').textContent(), 'geometry.min');
    assert.equal(request.source, entrySource, 'Run always starts with the entry source');
    assert.deepEqual(request.project, project({ 'main.min': entrySource, 'geometry.min': geometry42 }));
  });

  await measure('live dependency diagnostics select the correct tab and Unicode token range', async () => {
    await page.locator('#source').fill(brokenGeometry);
    await selectFile(page, 'main.min');
    const location = page.locator('.diagnostic-location').filter({ hasText: /^geometry\.min:2:/ });
    await location.waitFor({ state: 'visible', timeout: COLD_TIMEOUT });
    const issue = await page.evaluate(() => window.__projectTrace.filter(row => row.kind === 'reply' && row.type === 'result')
      .flatMap(row => row.diagnostics ?? []).findLast(problem => problem.file === 'geometry.min'));
    assert.ok(issue);
    const token = '"wrong"';
    const tokenOffset = brokenGeometry.indexOf(token);
    const beforeToken = brokenGeometry.slice(brokenGeometry.indexOf('\n') + 1, tokenOffset);
    assert.equal(issue.line, 2);
    assert.equal(issue.column, [...beforeToken].length + 1, 'compiler columns count scalar values before the astral character');
    assert.equal(issue.endLine, 2);
    assert.equal(issue.endColumn, issue.column + token.length);
    assert.equal(await page.locator('#source-filename').textContent(), 'main.min', 'a result must not move the active file');
    await location.click();
    assert.equal(await page.locator('#source-filename').textContent(), 'geometry.min');
    const selection = await page.locator('#source').evaluate(element => ({ start: element.selectionStart,
      end: element.selectionEnd, value: element.value.slice(element.selectionStart, element.selectionEnd) }));
    assert.deepEqual(selection, { start: tokenOffset, end: tokenOffset + token.length, value: token });
    assert.equal(await page.locator('#source').evaluate(element => element === document.activeElement), true);
  });

  await measure('editing only a dependency changes entry output and supports the Run shortcut', async () => {
    await page.locator('#source').fill(geometry43);
    const request = await run(page, '43\n', true);
    assert.equal(request.source, entrySource);
    assert.deepEqual(request.project, project({ 'main.min': entrySource, 'geometry.min': geometry43 }));
  });

  await measure('switching tabs preserves current output, download and request revision', async () => {
    const before = await page.evaluate(() => window.__projectTrace.filter(row => row.kind === 'request').length);
    assert.equal(await page.locator('#download').isVisible(), true);
    const note = await page.locator('#output-note').textContent();
    await selectFile(page, 'main.min');
    assert.equal(await page.locator('#source').inputValue(), entrySource);
    await selectFile(page, 'geometry.min', { keyboard: true });
    assert.equal(await page.locator('#source').inputValue(), geometry43);
    assert.equal(await page.locator('#output').textContent(), '43\n');
    assert.equal(await page.locator('#output-note').textContent(), note);
    assert.equal(await page.locator('#download').isVisible(), true);
    await page.clock.install();
    await page.clock.fastForward(850);
    assert.equal(await page.evaluate(() => window.__projectTrace.filter(row => row.kind === 'request').length), before,
      'file selection must not queue another check');
  });

  await measure('out-of-order additions sort tabs and reload preserves all files plus active selection', async () => {
    await addFile(page, 'zeta.min', '// The last tab.\n');
    await addFile(page, 'alpha.min', '// The first tab.\n');
    assert.deepEqual(await paths(page), ['alpha.min', 'geometry.min', 'main.min', 'zeta.min']);
    await selectFile(page, 'geometry.min');
    sharedProject = project({ 'main.min': entrySource, 'geometry.min': geometry43,
      'alpha.min': '// The first tab.\n', 'zeta.min': '// The last tab.\n' });
    await waitForDraft(page, sharedProject, 'geometry.min');
    await page.reload({ waitUntil: 'load' });
    await ready(page);
    assert.deepEqual(await paths(page), sharedProject.files.map(file => file.path));
    assert.equal(await page.locator('#source-filename').textContent(), 'geometry.min');
    assert.equal(await page.locator('#source').inputValue(), geometry43);
    for (const file of sharedProject.files) {
      await selectFile(page, file.path);
      assert.equal(await page.locator('#source').inputValue(), file.source);
    }
    await selectFile(page, 'geometry.min');
    await waitForDraft(page, sharedProject, 'geometry.min');
  });

  await measure('Share copies a version-two project containing every source file', async () => {
    await page.locator('#share').click();
    await page.locator('#share-url').waitFor({ state: 'visible' });
    await page.waitForFunction(() => document.getElementById('share-url').value.includes('#minyar=v2.'));
    sharedURL = await page.locator('#share-url').inputValue();
    const address = new URL(sharedURL);
    assert.equal(address.origin, origin);
    assert.equal(address.pathname, mount);
    assert.equal(address.search, '');
    assert.match(address.hash, /^#minyar=v2\.p\./);
    assert.equal(await page.locator('#share-url').getAttribute('readonly') !== null, true);
    await page.locator('#share-message').filter({ hasText: /copied/i }).waitFor();
    assert.equal(await page.evaluate(() => navigator.clipboard.readText()), sharedURL);
  });

  const sharedContext = await contextFor('shared');
  const shared = await open(sharedContext, sharedURL);
  currentPage = shared;
  await measure('opening and viewing all shared files preserves the old draft without compiler work', async () => {
    await shared.locator('#share-message').filter({ hasText: /shared.*loaded|shared.*ready/i }).waitFor();
    assert.deepEqual(await paths(shared), sharedProject.files.map(file => file.path));
    for (const file of sharedProject.files) {
      await selectFile(shared, file.path);
      assert.equal(await shared.locator('#source').inputValue(), file.source);
    }
    await noAutomaticWork(shared);
    assert.deepEqual(JSON.parse(await stored(shared)), legacyDraft);
  });

  await measure('explicitly running an unchanged shared project still preserves the old draft', async () => {
    await selectFile(shared, 'geometry.min');
    const request = await run(shared, '43\n');
    assert.deepEqual(request.project, sharedProject);
    assert.deepEqual(JSON.parse(await stored(shared)), legacyDraft);
  });

  await measure('editing a shared dependency adopts the whole project and survives reload', async () => {
    await shared.locator('#source').fill(geometry44);
    const adopted = project(Object.fromEntries(sharedProject.files.map(file => [file.path,
      file.path === 'geometry.min' ? geometry44 : file.source])));
    await waitForDraft(shared, adopted, 'geometry.min');
    assert.equal(new URL(shared.url()).hash, '', 'an edited project must clear its stale share fragment');
    await shared.reload({ waitUntil: 'load' });
    await ready(shared);
    assert.equal(await shared.locator('#source-filename').textContent(), 'geometry.min');
    assert.equal(await shared.locator('#source').inputValue(), geometry44);
    assert.deepEqual(await paths(shared), adopted.files.map(file => file.path));
    await run(shared, '44\n');
  });
  await sharedContext.close();
  currentPage = page;

  const coordinatesContext = await contextFor('shared-source-coordinates');
  const bareCRSource = 'print(\rmissing)\n';
  const bareCRProject = project({ 'main.min': bareCRSource, 'notes.min': '// A shared project.\n' });
  const bareCRPage = await open(coordinatesContext, await sharedProjectURL(page, bareCRProject));
  await measure('a shared raw CR entry maps compiler line one to the displayed missing token on line two', async () => {
    await bareCRPage.locator('#share-message').filter({ hasText: /shared.*loaded|shared.*ready/i }).waitFor();
    const displayed = bareCRSource.replace(/\r\n?/g, '\n');
    assert.equal(await bareCRPage.locator('#source').inputValue(), displayed);
    assert.equal(displayed.split('\n')[1], 'missing)');
    await noAutomaticWork(bareCRPage);
    const { request, result } = await requestRun(bareCRPage);
    assert.equal(request.source, bareCRSource, 'Run receives the original raw CR entry source');
    assert.deepEqual(request.project, bareCRProject);
    assert.equal(result.exitCode, 1);
    assert.equal(result.output, '');
    const issue = result.diagnostics.find(problem => problem.file === 'main.min');
    assert.ok(issue);
    assert.equal(issue.line, 1, 'the compiler treats a bare CR as whitespace on its original line');
    assert.equal(issue.column, [...bareCRSource.slice(0, bareCRSource.indexOf('missing'))].length + 1);
    const location = bareCRPage.locator('.diagnostic-location').filter({ hasText: /^main\.min:1:/ });
    await location.waitFor({ state: 'visible' });
    await location.click();
    const selection = await bareCRPage.locator('#source').evaluate(element => ({
      start: element.selectionStart, end: element.selectionEnd,
      text: element.value.slice(element.selectionStart, element.selectionEnd),
      focused: element === document.activeElement,
    }));
    assert.deepEqual(selection, { start: displayed.indexOf('missing'), end: displayed.indexOf('missing') + 'missing'.length,
      text: 'missing', focused: true });
    assert.deepEqual(JSON.parse(await stored(bareCRPage)), legacyDraft, 'diagnostic navigation must not adopt a viewed shared project');
  });
  await bareCRPage.close();

  const crlfGeometry = brokenGeometry.replaceAll('\n', '\r\n');
  const crlfProject = project({ 'main.min': entrySource, 'geometry.min': crlfGeometry });
  const crlfPage = await open(coordinatesContext, await sharedProjectURL(page, crlfProject));
  await measure('a shared imported CRLF dependency selects the correct token after an astral character', async () => {
    await crlfPage.locator('#share-message').filter({ hasText: /shared.*loaded|shared.*ready/i }).waitFor();
    await noAutomaticWork(crlfPage);
    const { request, result } = await requestRun(crlfPage);
    assert.deepEqual(request.project, crlfProject, 'the dependency remains byte-for-byte CRLF source');
    assert.equal(result.exitCode, 1);
    assert.equal(result.output, '');
    const issue = result.diagnostics.find(problem => problem.file === 'geometry.min');
    assert.ok(issue);
    const token = '"wrong"';
    const prefix = crlfGeometry.slice(crlfGeometry.indexOf('\n') + 1, crlfGeometry.indexOf(token));
    assert.equal(issue.line, 2);
    assert.equal(issue.column, [...prefix].length + 1);
    assert.ok(issue.column < prefix.length + 1, 'the preceding astral character occupies two textarea code units');
    assert.equal(issue.endLine, 2);
    assert.equal(issue.endColumn, issue.column + token.length);
    assert.equal(await crlfPage.locator('#source-filename').textContent(), 'main.min');
    const location = crlfPage.locator('.diagnostic-location').filter({ hasText: /^geometry\.min:2:/ });
    await location.waitFor({ state: 'visible' });
    await location.click();
    const displayed = crlfGeometry.replaceAll('\r\n', '\n');
    assert.equal(await crlfPage.locator('#source-filename').textContent(), 'geometry.min');
    assert.equal(await crlfPage.locator('#source').inputValue(), displayed);
    const selection = await crlfPage.locator('#source').evaluate(element => ({
      start: element.selectionStart, end: element.selectionEnd,
      text: element.value.slice(element.selectionStart, element.selectionEnd),
      focused: element === document.activeElement,
    }));
    assert.deepEqual(selection, { start: displayed.indexOf(token), end: displayed.indexOf(token) + token.length,
      text: token, focused: true });
    assert.deepEqual(JSON.parse(await stored(crlfPage)), legacyDraft);
  });
  await coordinatesContext.close();
  currentPage = page;

  const customContext = await contextFor('custom-shared-project-reset');
  const customEntry = 'nested/entry.min';
  const customDependency = 'nested/geometry.min';
  const originalCustom = { ...project({ [customEntry]: namespaceExample.source, [customDependency]: geometry42 }), entry: customEntry };
  const customURL = await sharedProjectURL(page, originalCustom);
  assert.equal(new URLSearchParams(new URL(customURL).hash.slice(1)).has('example'), false,
    'this project has no known tour or catalog identity');
  const custom = await open(customContext, customURL);
  await measure('Reset preserves a custom shared project and its nested entry, then adopts a restored draft baseline', async () => {
    await custom.locator('#share-message').filter({ hasText: /shared.*loaded|shared.*ready/i }).waitFor();
    await noAutomaticWork(custom);
    assert.deepEqual(await paths(custom), [customEntry, customDependency]);
    assert.equal(await custom.locator('#source-filename').textContent(), customEntry);
    assert.equal(await custom.locator('#source').inputValue(), namespaceExample.source);
    assert.match(await custom.locator('#project-entry').textContent(), /nested\/entry\.min/);
    assert.equal(await custom.locator('#project-remove').isDisabled(), true);
    assert.equal(await custom.locator('#supporting-files').isVisible(), false,
      'a custom project is not the reviewed single-file guide fragment');

    await selectFile(custom, customDependency);
    await custom.locator('#source').fill(geometry43);
    const changedCustom = { ...originalCustom, files: originalCustom.files.map(file => ({ ...file,
      source: file.path === customDependency ? geometry43 : file.source })) };
    assert.deepEqual((await run(custom, '43\n')).project, changedCustom);
    await waitForDraft(custom, changedCustom, customDependency);

    await custom.locator('#reset').click();
    assert.deepEqual(await paths(custom), [customEntry, customDependency], 'Reset keeps both original files');
    assert.equal(await custom.locator('#source-filename').textContent(), customEntry);
    assert.equal(await custom.locator('#source').inputValue(), namespaceExample.source);
    await selectFile(custom, customDependency);
    assert.equal(await custom.locator('#source').inputValue(), geometry42, 'Reset restores the shared dependency, not its edited version');
    const restored = await run(custom, '42\n');
    assert.equal(restored.source, namespaceExample.source);
    assert.deepEqual(restored.project, originalCustom, 'Reset preserves the non-main entry and the complete immutable shared baseline');

    await custom.locator('#share').click();
    await custom.locator('#share-url').waitFor({ state: 'visible' });
    await custom.waitForFunction(() => document.getElementById('share-url').value.includes('#minyar=v2.p.'));
    const resetLink = await custom.locator('#share-url').inputValue();
    const viewed = await open(customContext, resetLink);
    await viewed.locator('#share-message').filter({ hasText: /shared.*loaded|shared.*ready/i }).waitFor();
    assert.deepEqual(await paths(viewed), [customEntry, customDependency]);
    assert.equal(await viewed.locator('#source-filename').textContent(), customEntry);
    assert.equal(await viewed.locator('#source').inputValue(), namespaceExample.source);
    assert.match(await viewed.locator('#project-entry').textContent(), /nested\/entry\.min/);
    await selectFile(viewed, customDependency);
    assert.equal(await viewed.locator('#source').inputValue(), geometry42, 'the new v2 link includes the original restored companion');
    await noAutomaticWork(viewed);
    await viewed.close();
    currentPage = custom;

    // A later reload begins a new editing session from the saved draft. As
    // with legacy custom drafts, that restored project is the Reset baseline.
    await custom.locator('#source').fill(geometry43);
    await waitForDraft(custom, changedCustom, customDependency);
    assert.equal(new URL(custom.url()).hash, '');
    await custom.reload({ waitUntil: 'load' });
    await ready(custom);
    assert.equal(await custom.locator('#source-filename').textContent(), customDependency);
    assert.equal(await custom.locator('#source').inputValue(), geometry43);
    await custom.locator('#source').fill(geometry44);
    await custom.locator('#reset').click();
    assert.deepEqual(await paths(custom), [customEntry, customDependency]);
    assert.equal(await custom.locator('#source-filename').textContent(), customEntry);
    assert.equal(await custom.locator('#source').inputValue(), namespaceExample.source);
    await selectFile(custom, customDependency);
    assert.equal(await custom.locator('#source').inputValue(), geometry43, 'a restored custom draft keeps its own complete baseline');
    assert.deepEqual((await run(custom, '43\n')).project, changedCustom);
  });
  await customContext.close();
  currentPage = page;

  const companionContext = await contextFor('explicit-guide-companion');
  const companion = await open(companionContext);
  await measure('an explicit guide action adds a visible companion, runs 42 and shares the unchanged excerpt', async () => {
    await companion.locator(`#language-list button[data-example-id="${namespaceExample.id}"]`).click();
    assert.equal(await companion.locator('#source').inputValue(), namespaceExample.source);
    assert.deepEqual(await paths(companion), ['main.min']);
    assert.equal(await companion.locator('#run').isDisabled(), true, 'the original excerpt alone remains contextual');
    assert.equal(await companion.locator('#supporting-files').isVisible(), true);
    const addCompanion = companion.getByRole('button', { name: 'Add geometry.min', exact: true });
    assert.equal(await addCompanion.getAttribute('id'), 'open-supporting-files');
    assert.equal(await addCompanion.isVisible(), true);

    await companion.locator('#source').fill(namespaceExample.source + '// An explicit edit changes this context.\n');
    assert.equal(await companion.locator('#supporting-files').isVisible(), false);
    assert.equal(await addCompanion.isVisible(), false, 'an edited excerpt cannot offer the reviewed original companion action');
    assert.match(await companion.locator('#example-provenance').textContent(), /edited in this browser/);
    await companion.locator('#reset').click();
    assert.equal(await companion.locator('#source').inputValue(), namespaceExample.source);
    assert.deepEqual(await paths(companion), ['main.min']);
    assert.equal(await companion.locator('#run').isDisabled(), true);
    assert.equal(await addCompanion.isVisible(), true, 'Reset restores the exact single-file excerpt and its explicit action');

    await addCompanion.click();
    const value = project({ 'main.min': namespaceExample.source, 'geometry.min': geometry42 });
    assert.deepEqual(await paths(companion), ['geometry.min', 'main.min']);
    assert.equal(await companion.locator('#source-filename').textContent(), 'main.min');
    assert.equal(await companion.locator('#source').inputValue(), namespaceExample.source,
      'adding support leaves every original main.min byte untouched');
    assert.equal(await companion.locator('#supporting-files').isVisible(), false);
    assert.equal(await addCompanion.isVisible(), false);
    assert.match(await companion.locator('#example-provenance').textContent(), /exact original source · project files changed/);
    assert.doesNotMatch(await companion.locator('#example-provenance').textContent(), /edited in this browser/);
    await selectFile(companion, 'geometry.min');
    assert.equal(await companion.locator('#source').inputValue(), geometry42);
    assert.match(await companion.locator('#source').inputValue(), /^public record Point/);
    assert.match(await companion.locator('#source').inputValue(), /public function answer\(point: Point\): Integer/);
    const request = await run(companion, '42\n'); // x = 20, y = 22; the visible function returns their sum.
    assert.deepEqual(request.project, value);
    assert.equal(request.source, namespaceExample.source, 'Run from the companion tab still compiles the untouched entry');
    await waitForDraft(companion, value, 'geometry.min');

    await companion.locator('#share').click();
    await companion.locator('#share-url').waitFor({ state: 'visible' });
    await companion.waitForFunction(() => document.getElementById('share-url').value.includes('#minyar=v2.p.'));
    const address = await companion.locator('#share-url').inputValue();
    assert.match(new URL(address).hash, /^#minyar=v2\.p\./);
    const viewed = await open(companionContext, address);
    await viewed.locator('#share-message').filter({ hasText: /shared.*loaded|shared.*ready/i }).waitFor();
    assert.deepEqual(await paths(viewed), ['geometry.min', 'main.min']);
    await selectFile(viewed, 'main.min');
    assert.equal(await viewed.locator('#source').inputValue(), namespaceExample.source,
      'the shared project round trip retains the exact original excerpt');
    await selectFile(viewed, 'geometry.min');
    assert.equal(await viewed.locator('#source').inputValue(), geometry42);
    assert.equal(await viewed.locator('#supporting-files').isVisible(), false);
    await noAutomaticWork(viewed);
    await viewed.close();
    currentPage = companion;

    await companion.locator('#reset').click();
    assert.deepEqual(await paths(companion), ['main.min']);
    assert.equal(await companion.locator('#source').inputValue(), namespaceExample.source);
    assert.equal(await companion.locator('#run').isDisabled(), true);
    assert.equal(await addCompanion.isVisible(), true);
    const provenance = await companion.locator('#example-provenance').textContent();
    assert.match(provenance, /exact original source/);
    assert.doesNotMatch(provenance, /project files changed|edited in this browser/);
  });
  await companionContext.close();
  currentPage = page;

  await measure('invalid paths and duplicate names leave project contents and selection intact', async () => {
    const before = await paths(page);
    const active = await page.locator('#source-filename').textContent();
    const source = await page.locator('#source').inputValue();
    const invalid = ['../escape.min', '/absolute.min', 'C:/drive.min', 'nested//empty.min', './dot.min',
      'folder\\backslash.min', 'library/io.min', 'wrong.txt', 'geometry.min', 'geometry.min/child.min',
      'x'.repeat(257) + '.min'];
    for (const filename of invalid) {
      await openAdd(page);
      await page.locator('#project-path').fill(filename);
      await page.locator('#project-add').click();
      assert.ok((await page.locator('#project-message').textContent()).trim(), `${filename}: explain the rejection`);
      assert.deepEqual(await paths(page), before);
      assert.equal(await page.locator('#source-filename').textContent(), active);
      assert.equal(await page.locator('#source').inputValue(), source);
    }
  });

  await measure('removing a dependency invalidates output and Undo restores its exact source', async () => {
    await run(page, '43\n');
    await selectFile(page, 'geometry.min');
    await page.locator('#project-remove').click();
    assert.deepEqual(await paths(page), ['alpha.min', 'main.min', 'zeta.min']);
    assert.equal(await page.locator('#source-filename').textContent(), 'main.min');
    assert.equal(await page.locator('#project-remove').isDisabled(), true);
    assert.equal(await page.locator('#project-undo').isVisible(), true);
    assert.equal(await page.locator('#download').isVisible(), false);
    assert.match(await page.locator('#output-note').textContent(), /earlier|changed|changes/i);
    await page.locator('#project-undo').click();
    assert.equal(await page.locator('#source-filename').textContent(), 'geometry.min');
    assert.equal(await page.locator('#source').inputValue(), geometry43);
    assert.equal(await page.locator('#project-undo').isVisible(), false);
    await run(page, '43\n');
  });

  await measure('adding a file clears one-level removal Undo and entry removal stays protected', async () => {
    await selectFile(page, 'alpha.min');
    await page.locator('#project-remove').click();
    assert.equal(await page.locator('#project-undo').isVisible(), true);
    await addFile(page, 'replacement.min', '// An explicit new file.\n');
    assert.equal(await page.locator('#project-undo').isVisible(), false);
    assert.equal((await paths(page)).includes('alpha.min'), false);
    await selectFile(page, 'main.min');
    assert.equal(await page.locator('#project-remove').isDisabled(), true);
    const before = await paths(page);
    await page.locator('#project-remove').evaluate(button => button.click());
    assert.deepEqual(await paths(page), before);
  });

  await measure('Reset and selecting a tour replace the project with a single main file', async () => {
    await page.locator('#reset').click();
    assert.deepEqual(await paths(page), ['main.min']);
    assert.equal(await page.locator('#source').inputValue(), tour[0].source);
    assert.equal(await page.locator('#project-undo').isVisible(), false);
    await addFile(page, 'temporary.min', '// This belongs to the previous project.\n');
    await page.getByRole('button', { name: tour[1].title, exact: true }).click();
    assert.deepEqual(await paths(page), ['main.min']);
    assert.equal(await page.locator('#source').inputValue(), tour[1].source);
    assert.equal(await page.locator('#source-filename').textContent(), 'main.min');
    const request = await run(page, tour[1].expected);
    assert.equal(Object.hasOwn(request, 'project'), false, 'single-file tour returns to the legacy protocol');
  });

  const capacityFiles = { 'main.min': 'print(42)\n' };
  for (let index = 1; index < 16; index++) capacityFiles[`part-${String(index).padStart(2, '0')}.min`] = `// Module ${index}.\n`;
  capacityFiles['part-01.min'] = '// Original CRLF source.\r\n// Keep these bytes until explicitly edited.\r\n';
  const capacityContext = await contextFor('capacity', projectDraft(capacityFiles, 'part-15.min'));
  const capacity = await open(capacityContext);
  await measure('the sixteenth file works and a forced seventeenth submission is rejected', async () => {
    assert.equal((await paths(capacity)).length, 16);
    assert.equal(await capacity.locator('#source-filename').textContent(), 'part-15.min');
    await selectFile(capacity, 'part-01.min', { keyboard: true });
    assert.equal(await capacity.locator('#source').inputValue(), capacityFiles['part-01.min'].replaceAll('\r\n', '\n'),
      'the textarea displays normalized line endings without changing stored source');
    await selectFile(capacity, 'part-15.min');
    await waitForDraft(capacity, project(capacityFiles), 'part-15.min');
    await openAdd(capacity);
    assert.equal(await capacity.locator('#project-add').isDisabled(), true);
    await capacity.locator('#project-path').fill('overflow.min');
    // The disabled button is the ordinary guard; direct form submission also
    // has to reach the model's limit check without mutating the editor.
    await capacity.locator('#project-file-form').evaluate(form => form.requestSubmit());
    assert.match(await capacity.locator('#project-message').textContent(), /16/);
    assert.equal((await paths(capacity)).length, 16);
    assert.equal(await capacity.locator('#source-filename').textContent(), 'part-15.min');
    await capacity.locator('#project-remove').click();
    assert.equal(await capacity.locator('#project-add').isEnabled(), true);
    await addFile(capacity, 'overflow.min');
    assert.equal((await paths(capacity)).length, 16);
    assert.equal(await capacity.locator('#project-undo').isVisible(), false);
    const request = await run(capacity, '42\n');
    assert.equal(request.project.files.find(file => file.path === 'part-01.min').source, capacityFiles['part-01.min'],
      'tab selection and unrelated add/remove operations retain original CRLF project bytes');
  });
  await capacityContext.close();

  const comment = size => '//' + 'x'.repeat(size - 3) + '\n';
  const halfBudget = comment(32 * 1024);
  const budgetFiles = { 'main.min': halfBudget, 'notes.min': halfBudget };
  assert.equal(Buffer.byteLength(halfBudget) * 2, 64 * 1024);
  const budgetContext = await contextFor('budget', projectDraft(budgetFiles, 'notes.min'));
  const budget = await open(budgetContext);
  await measure('the combined UTF-8 budget blocks execution and saving without truncating an edit', async () => {
    const before = await stored(budget);
    assert.equal(await budget.locator('#run').isEnabled(), true, 'the exact 64 KiB project is valid');
    const tooLarge = halfBudget + '🌙';
    assert.equal(Buffer.byteLength(halfBudget) + Buffer.byteLength(tooLarge), 64 * 1024 + 4);
    await budget.locator('#source').fill(tooLarge);
    assert.equal(await budget.locator('#source').inputValue(), tooLarge);
    assert.equal(await budget.locator('#run').isDisabled(), true);
    assert.equal(await budget.locator('#source-info').locator('..').getAttribute('data-over-limit'), 'true');
    await budget.clock.install();
    await budget.clock.fastForward(850);
    assert.equal(await stored(budget), before, 'invalid aggregate source must not replace the last valid draft');
    if (await budget.locator('#share').isEnabled()) {
      await budget.locator('#share').click();
      await budget.locator('#share-message').filter({ hasText: /UTF-8|byte limit|64\s*KiB|too (?:large|long)/i }).waitFor();
    }
    assert.equal(await budget.locator('#share-url').isVisible(), false);
    await budget.locator('#source').fill(halfBudget);
    await waitForDraft(budget, project(budgetFiles), 'notes.min');
    await run(budget, '');
  });
  await budgetContext.close();

  const hostileText = '</textarea><img src=x onerror=globalThis.__projectXSS=true><script>globalThis.__projectXSS=true</script>';
  const hostileSource = `print("${hostileText}")\n`;
  const safeContext = await contextFor('escaped-source', { version: 1, exampleId: 'hello', source: hostileSource });
  const safe = await open(safeContext);
  const hostilePath = '<svg onload=globalThis.__projectXSS=true>.min';
  await measure('source, output and project filenames render as text without HTML execution', async () => {
    assert.equal(await safe.locator('#source').inputValue(), hostileSource);
    await addFile(safe, hostilePath, `// ${hostileText}\n`);
    assert.ok((await paths(safe)).includes(hostilePath));
    assert.equal(await safe.locator('#source-filename').textContent(), hostilePath);
    await run(safe, hostileText + '\n');
    assert.equal(await safe.locator('#output').textContent(), hostileText + '\n');
    assert.equal(await safe.locator('#output img, #output script, #project-files svg, #source-filename svg').count(), 0);
    assert.equal(await safe.evaluate(() => globalThis.__projectXSS), undefined);
    await safe.screenshot({ path: path.join(evidence, 'projects-desktop.png'), fullPage: true });
  });

  await measure('project tabs, path form and source fit a 390px viewport', async () => {
    await addFile(safe, 'nested/' + 'long-module-name-'.repeat(9) + '星.min', '// A long path still fits.\n');
    await safe.setViewportSize({ width: 390, height: 844 });
    await openAdd(safe);
    await safe.locator('#project-path').fill('another/' + 'long-name-'.repeat(12) + 'moon.min');
    const width = await safe.evaluate(() => ({ viewport: document.documentElement.clientWidth,
      document: document.documentElement.scrollWidth, body: document.body.scrollWidth }));
    assert.ok(width.document <= width.viewport + 1, JSON.stringify(width));
    assert.ok(width.body <= width.viewport + 1, JSON.stringify(width));
    assert.equal(await safe.locator('#source').isVisible(), true);
    assert.equal(await safe.locator('#project-add').isEnabled(), true);
    await safe.screenshot({ path: path.join(evidence, 'projects-mobile.png'), fullPage: true });
  });
  await safeContext.close();
  currentPage = page;

  assert.deepEqual(failures.network, [], 'all browser requests stay on the self-contained site origin');
  assert.deepEqual(failures.http, [], 'all static assets resolve beneath the nested site path');
  assert.deepEqual(failures.page, [], 'project interactions produce no uncaught page errors');
  assert.deepEqual(failures.console, [], 'successful project flows produce no console errors');
  const payload = new URLSearchParams(new URL(sharedURL).hash.slice(1)).get('minyar').split('.').at(-1);
  assert.ok(requests.every(url => !url.includes(privateMarker) && !url.includes('minyar=') && !url.includes(payload)),
    'project source and share fragments must never be sent in HTTP request URLs');
  report.passed = true;
  console.log(`PASS ${checks.length} independent Chromium project flows`);
} catch (error) {
  report.passed = false;
  report.error = { message: error.message, stack: error.stack };
  if (currentPage && !currentPage.isClosed()) {
    await currentPage.screenshot({ path: path.join(evidence, 'projects-browser-failure.png'), fullPage: true }).catch(() => {});
    report.failureState = await currentPage.evaluate(key => ({
      filename: document.getElementById('source-filename')?.textContent,
      tabs: [...document.querySelectorAll('#project-files button[data-path]')].map(button => button.dataset.path),
      status: document.getElementById('status')?.textContent,
      projectMessage: document.getElementById('project-message')?.textContent,
      shareMessage: document.getElementById('share-message')?.textContent,
      output: document.getElementById('output')?.textContent,
      savedDraftVersion: JSON.parse(localStorage.getItem(key))?.version,
      trace: window.__projectTrace?.map(({ kind, worker, id, type, phase, message, diagnostics, exitCode }) =>
        ({ kind, worker, id, type, phase, message, diagnostics, exitCode })),
    }), DRAFT_KEY).catch(() => null);
  }
  throw error;
} finally {
  report.finishedAt = new Date().toISOString();
  report.requests = requests;
  report.failures = failures;
  await writeFile(path.join(evidence, 'projects-browser.json'), JSON.stringify(report, null, 2) + '\n');
  await browser?.close();
  server.closeAllConnections();
  await new Promise((resolve, reject) => server.close(error => error ? reject(error) : resolve()));
}
