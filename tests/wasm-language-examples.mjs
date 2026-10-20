import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFile, writeFile, mkdir, mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { isMainThread, parentPort, Worker } from 'node:worker_threads';

const root = fileURLToPath(new URL('../', import.meta.url));
const generator = path.join(root, 'tools/playground-language-examples.py');
const documentFile = path.join(root, 'docs/language.md');
const catalogFile = path.join(root, 'build/playground/language-examples.json');
const evidenceDirectory = path.join(root, 'build/wasm-evidence');
const sha256 = (bytes) => createHash('sha256').update(bytes).digest('hex');

async function engineWorker() {
  const engineUrl = new URL('../build/playground/engine.mjs', import.meta.url);
  const { createEngine } = await import(engineUrl.href);
  let activeId = null;
  const engine = await createEngine({
    loadBytes: (filename) => readFile(new URL(filename, engineUrl)),
    progress: (message, phase) => parentPort.postMessage({ type: 'progress', id: activeId, phase, message }),
  });
  parentPort.on('message', async ({ id, source }) => {
    activeId = id;
    try {
      const result = await engine.request('run', source);
      parentPort.postMessage({ type: 'result', id, result: {
        diagnostics: result.diagnostics, output: result.output, exitCode: result.exitCode,
        compileMs: result.compileMs, runMs: result.runMs,
        wasmBytes: result.wasm?.byteLength ?? 0,
        validWasm: result.wasm instanceof Uint8Array && WebAssembly.validate(result.wasm),
      } });
    } catch (error) {
      parentPort.postMessage({ type: 'error', id, message: error.message, stack: error.stack });
    } finally {
      activeId = null;
    }
  });
}

function generate(args = []) {
  const result = spawnSync('python3', [generator, ...args], {
    cwd: root, encoding: 'utf8', timeout: 10_000, maxBuffer: 4 * 1024 * 1024,
  });
  assert.ifError(result.error);
  assert.equal(result.signal, null, 'the catalog generator must not hang');
  return result;
}

async function generatorControls() {
  const directory = await mkdtemp(path.join(tmpdir(), 'minyar-language-catalog-'));
  const document = path.join(directory, 'fixture.md');
  const output = path.join(directory, 'fixture.json');
  const original = '  print("Exact 🌙\u2028source")\r\n';
  const fence = `~~~minyar\r\n${original}~~~~\r\n`;
  const ignored = '````text\r\n```minyar\r\nprint("not an example")\r\n```\r\n````\r\n';
  const base = `# A fixture\r\n\r\n## A stable section\r\n\r\n${fence}${ignored}`;
  async function inspect(contents) {
    await writeFile(document, contents);
    const result = generate(['--document', document, '--stdout']);
    assert.equal(result.status, 0, result.stderr);
    return JSON.parse(result.stdout);
  }
  try {
    const first = await inspect(base);
    assert.equal(first.examples.length, 1, 'minyar-looking fences inside another fenced block are not examples');
    assert.equal(first.examples[0].source, original, 'CRLF, indentation and Unicode separators must remain exact');
    assert.equal(first.examples[0].line, 6);
    assert.equal(first.examples[0].endLine, 6, 'Unicode separators inside Text do not advance file line numbers');
    assert.equal(first.examples[0].classification, 'unreviewed');
    assert.equal(first.examples[0].runnable, false, 'new code must never become runnable by a heuristic');
    assert.equal(Object.hasOwn(first.examples[0], 'expected'), false, 'new output must never be guessed');
    const shifted = await inspect(`An introduction.\r\n\r\n${base}`);
    assert.equal(shifted.examples[0].id, first.examples[0].id, 'moving a source block preserves its stable identity');
    assert.equal(shifted.examples[0].line, first.examples[0].line + 2);
    const duplicate = await inspect(base + fence);
    assert.equal(duplicate.examples.length, 2, 'identical code blocks must not be deduplicated');
    assert.equal(duplicate.examples[0].id, first.examples[0].id);
    assert.equal(duplicate.examples[1].id, `${first.examples[0].id}-2`);
    const changed = await inspect(base.replace('Exact 🌙', 'Changed 🌙'));
    assert.notEqual(changed.examples[0].id, first.examples[0].id, 'changed source receives a new identity and review');
    assert.equal(changed.examples[0].classification, 'unreviewed');
    await writeFile(document, base);
    const written = generate(['--document', document, '--output', output]);
    assert.equal(written.status, 0, written.stderr);
    const unreviewed = generate(['--document', document, '--output', output, '--check']);
    assert.equal(unreviewed.status, 1);
    assert.match(unreviewed.stderr, /classify new or changed blocks/, 'an up-to-date but unreviewed catalog cannot pass');
    const previous = Buffer.from('previous reviewed catalog bytes\n');
    await writeFile(output, previous);
    const guarded = generate(['--document', document, '--output', output, '--require-reviewed']);
    assert.equal(guarded.status, 1);
    assert.match(guarded.stderr, /classify new or changed blocks/);
    assert.deepEqual(await readFile(output), previous, 'unreviewed source must not overwrite an existing catalog');
    const missingOutput = path.join(directory, 'not-created.json');
    const guardedMissing = generate(['--document', document, '--output', missingOutput, '--require-reviewed']);
    assert.equal(guardedMissing.status, 1);
    await assert.rejects(readFile(missingOutput), { code: 'ENOENT' }, 'unreviewed source must not create a new catalog');
    const guardedStdout = generate(['--document', document, '--stdout', '--require-reviewed']);
    assert.equal(guardedStdout.status, 1);
    assert.equal(guardedStdout.stdout, '', 'review-required mode must reject before emitting data');
    await writeFile(document, '# Broken\n```minyar\nprint(1)\n');
    const unclosed = generate(['--document', document, '--stdout']);
    assert.equal(unclosed.status, 1);
    assert.match(unclosed.stderr, /Unclosed minyar fence at line 2/);
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
}

function engineClient() {
  const worker = new Worker(new URL(import.meta.url));
  let requestId = 0;
  let pending = null;
  let timer = null;
  function fail(error) {
    clearTimeout(timer);
    const current = pending;
    pending = null;
    current?.reject(error);
  }
  function deadline(milliseconds, phase) {
    clearTimeout(timer);
    timer = setTimeout(() => {
      const name = pending?.name ?? 'example';
      fail(new Error(`${name}: ${phase} exceeded ${milliseconds} ms`));
      void worker.terminate();
    }, milliseconds);
  }
  worker.on('error', fail);
  worker.on('exit', (code) => {
    if (pending) fail(new Error(`The browser engine worker exited unexpectedly (${code})`));
  });
  worker.on('message', (message) => {
    if (!pending || message.id !== pending.id) return;
    if (message.type === 'progress' && message.phase === 'running' && !pending.running) {
      pending.running = true;
      deadline(10_000, 'execution');
      return;
    }
    if (message.type === 'error') {
      fail(new Error(`${pending.name}: ${message.message}\n${message.stack ?? ''}`));
      return;
    }
    if (message.type === 'result') {
      clearTimeout(timer);
      const current = pending;
      pending = null;
      current.resolve(message.result);
    }
  });
  return {
    run(example) {
      assert.equal(pending, null, 'catalog engine requests must be serial');
      return new Promise((resolve, reject) => {
        pending = { id: ++requestId, name: example.id, resolve, reject, running: false };
        deadline(120_000, 'preparation or compilation');
        // This is the exact catalog source; no prefix, suffix or scaffold.
        worker.postMessage({ id: pending.id, source: example.source });
      });
    },
    async close() {
      clearTimeout(timer);
      await worker.terminate();
    },
  };
}

async function main() {
  const current = generate(['--check', '--output', catalogFile]);
  assert.equal(current.status, 0, current.stderr);
  await generatorControls();
  const [documentBytes, catalogText] = await Promise.all([readFile(documentFile), readFile(catalogFile, 'utf8')]);
  const catalog = JSON.parse(catalogText);
  assert.equal(catalog.schemaVersion, 1);
  assert.equal(catalog.document.file, 'docs/language.md');
  assert.equal(catalog.document.sha256, sha256(documentBytes));
  const lines = documentBytes.toString('utf8').split('\n').map((line, index, all) => index < all.length - 1 ? line + '\n' : line);
  const openingLines = lines.flatMap((line, index) => /^ {0,3}(?:`{3,}|~{3,})minyar[ \t]*\r?\n?$/.test(line) ? [index + 1] : []);
  assert.deepEqual(catalog.examples.map((example) => example.fenceLine), openingLines,
    'every language-guide minyar fence must be cataloged exactly once in document order');
  const ids = new Set();
  const classifications = {};
  for (const example of catalog.examples) {
    assert.equal(ids.has(example.id), false, `duplicate stable ID ${example.id}`);
    ids.add(example.id);
    assert.equal(example.file, catalog.document.file);
    assert.equal(example.line, example.fenceLine + 1);
    assert.equal(example.closingFenceLine, example.endLine + 1);
    assert.equal(example.source, lines.slice(example.line - 1, example.endLine).join(''), `${example.id}: exact original document slice`);
    assert.equal(example.sourceSha256, sha256(Buffer.from(example.source, 'utf8')));
    assert.ok(example.id.startsWith('language-') && example.id.includes(example.sourceSha256.slice(0, 12)));
    assert.equal(example.heading, example.headings.at(-1));
    assert.ok(example.title.length > 0 && example.reason.length > 30);
    assert.notEqual(example.classification, 'unreviewed', `${example.id} needs an explicit classification`);
    assert.equal(Object.hasOwn(example, 'scaffold'), false);
    classifications[example.classification] = (classifications[example.classification] ?? 0) + 1;
    if (example.runnable) {
      assert.equal(example.classification, 'standalone');
      assert.equal(typeof example.expected, 'string');
      assert.equal(example.expectedExitCode, 0);
      assert.ok(example.expectedBasis.length > 30, 'every stdout expectation must explain its independent basis');
    } else {
      assert.ok(['fragment', 'test-mode', 'unsupported-host'].includes(example.classification));
      assert.equal(Object.hasOwn(example, 'expected'), false, 'excluded blocks must not pretend to have a standalone output oracle');
    }
  }
  const runnable = catalog.examples.filter((example) => example.runnable);
  assert.equal(catalog.summary.total, catalog.examples.length);
  assert.equal(catalog.summary.runnable, runnable.length);
  assert.deepEqual(catalog.summary.byClassification, classifications);
  assert.ok(runnable.some((example) => example.expected === ''), 'quiet declaration-only examples remain executable catalog entries');
  assert.ok(runnable.some((example) => example.expected !== ''), 'the runnable catalog must also exercise observable output');

  await mkdir(evidenceDirectory, { recursive: true });
  const report = {
    document: catalog.document, summary: catalog.summary, startedAt: new Date().toISOString(),
    sourcePolicy: 'Exact original documentation source; no source rewriting or scaffolding.',
    expectations: 'Reviewed literals, documentation comments and arithmetic, independent of runtime output.',
    tests: [],
    excluded: catalog.examples.filter((example) => !example.runnable).map(({ id, file, line, classification, reason }) => ({ id, file, line, classification, reason })),
  };
  const engine = engineClient();
  try {
    for (const example of runnable) {
      const result = await engine.run(example);
      assert.deepEqual(result.diagnostics, [], `${example.id}: ${JSON.stringify(result.diagnostics)}`);
      assert.equal(result.exitCode, example.expectedExitCode, `${example.id}: exit status`);
      assert.equal(result.output, example.expected, `${example.id}: stdout (${example.expectedBasis})`);
      assert.equal(result.validWasm, true, `${example.id}: valid compiled WebAssembly`);
      assert.ok(result.wasmBytes > 8, `${example.id}: nonempty compiled module`);
      report.tests.push({ id: example.id, file: example.file, line: example.line, title: example.title,
        compileMs: result.compileMs, runMs: result.runMs, wasmBytes: result.wasmBytes });
      console.log(`PASS ${example.id}: ${result.wasmBytes} B, compile ${result.compileMs.toFixed(1)} ms, run ${result.runMs.toFixed(1)} ms`);
    }
    report.passed = true;
  } catch (error) {
    report.passed = false;
    report.error = { message: error.message, stack: error.stack };
    throw error;
  } finally {
    await engine.close();
    report.finishedAt = new Date().toISOString();
    await writeFile(path.join(evidenceDirectory, 'language-examples.json'), JSON.stringify(report, null, 2) + '\n');
  }
  console.log(`PASS all ${catalog.examples.length} exact language-guide blocks cataloged; ${runnable.length} real browser-engine executions; ${report.excluded.length} explicit contextual exclusions`);
}

if (isMainThread) await main();
else await engineWorker();
