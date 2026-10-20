import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { isMainThread, parentPort, workerData, Worker } from 'node:worker_threads';
import { diagnosticSelection } from '../playground/app.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));
const sha256 = bytes => createHash('sha256').update(bytes).digest('hex');

// Exercise the shipped browser worker, including optional-project forwarding,
// with only the file-URL fetch adapter needed by Node's fetch implementation.
async function browserWorker() {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (input, options) => {
    const url = new URL(input instanceof Request ? input.url : String(input));
    if (url.protocol !== 'file:') return originalFetch(input, options);
    const bytes = await readFile(fileURLToPath(url));
    return new Response(bytes, { headers: {
      'content-type': url.pathname.endsWith('.wasm') ? 'application/wasm' : 'application/octet-stream',
      'content-length': String(bytes.byteLength),
    } });
  };
  globalThis.self = { postMessage: message => parentPort.postMessage(message) };
  await import(pathToFileURL(path.join(workerData.site, 'worker.mjs')).href);
  assert.equal(typeof self.onmessage, 'function', 'the actual browser worker installs its handler');
  parentPort.on('message', data => self.onmessage({ data }));
}

function engineClient() {
  const site = path.resolve(root, process.env.MINYAR_WASM_PROJECT_SITE ?? 'build/playground');
  const worker = new Worker(new URL(import.meta.url), { workerData: { site } });
  let serial = 0;
  let pending = null;
  let timer = null;
  let stopped = false;
  function fail(error) {
    clearTimeout(timer);
    const current = pending;
    pending = null;
    current?.reject(error);
  }
  function deadline(milliseconds, phase) {
    clearTimeout(timer);
    timer = setTimeout(() => {
      const name = pending?.name ?? 'project';
      stopped = true;
      fail(new Error(`${name}: ${phase} exceeded ${milliseconds} ms`));
      void worker.terminate();
    }, milliseconds);
  }
  worker.on('error', error => { stopped = true; fail(error); });
  worker.on('exit', code => {
    stopped = true;
    if (pending) fail(new Error(`The project worker exited unexpectedly (${code})`));
  });
  worker.on('message', message => {
    if (!pending || message.id !== pending.id) return;
    if (message.type === 'progress' && message.phase === 'running' && !pending.running) {
      pending.running = true;
      deadline(10_000, 'execution');
    } else if (message.type === 'error') {
      fail(new Error(`${pending.name}: ${message.message}`));
    } else if (message.type === 'result') {
      clearTimeout(timer);
      const current = pending;
      pending = null;
      current.resolve(message);
    }
  });
  return {
    request(name, type, source, project) {
      assert.equal(stopped, false, 'a stopped project worker cannot accept another request');
      assert.equal(pending, null, 'project requests are serial');
      return new Promise((resolve, reject) => {
        pending = { id: ++serial, name, resolve, reject, running: false };
        deadline(120_000, 'preparation or compilation');
        const message = { id: pending.id, type, source };
        if (project !== undefined) message.project = project;
        worker.postMessage(message);
      });
    },
    async close() {
      stopped = true;
      clearTimeout(timer);
      await worker.terminate();
    },
  };
}

function project(files, entry = 'main.min') {
  return { version: 1, entry, files: Object.entries(files).map(([path, source]) => ({ path, source })) };
}

function diagnosticSelectionControls() {
  const cases = [
    { name: 'CRLF before an astral character', source: 'print("first")\r\nprint("🌙", missing)\r\n',
      displayed: 'print("first")\nprint("🌙", missing)\n',
      coordinates: [2, 12, 2, 19], expected: { start: 27, end: 34 }, selected: 'missing' },
    { name: 'bare CR inside a parenthesized expression', source: 'print(\rmissing)\n',
      displayed: 'print(\nmissing)\n',
      coordinates: [1, 8, 1, 15], expected: { start: 7, end: 14 }, selected: 'missing' },
    { name: 'range crossing two CRLF boundaries', source: 'ab\r\ncd\r\nef',
      displayed: 'ab\ncd\nef',
      coordinates: [1, 2, 3, 2], expected: { start: 1, end: 7 }, selected: 'b\ncd\ne' },
    { name: 'LF preserves Unicode scalar columns', source: '🌙abc\nhello',
      displayed: '🌙abc\nhello',
      coordinates: [1, 2, 1, 4], expected: { start: 2, end: 4 }, selected: 'ab' },
  ];
  for (const value of cases) {
    const actual = diagnosticSelection(value.source, ...value.coordinates);
    assert.deepEqual(actual, value.expected, `${value.name}: displayed UTF-16 offsets`);
    assert.equal(value.displayed.slice(actual.start, actual.end), value.selected,
      `${value.name}: selected text matches the compiler token/range`);
  }
  return { name: 'compiler ranges map to textarea-normalized text', control: true, cases };
}

async function argumentSizeControls() {
  const site = path.resolve(root, process.env.MINYAR_WASM_PROJECT_SITE ?? 'build/playground');
  const { writeArgumentSizes } = await import(pathToFileURL(path.join(site, 'engine.mjs')).href);
  const memory = new WebAssembly.Memory({ initial: 1 });
  const args = ['minyarc', '星🌙 notes/main.min', 'output.ll'];
  const expectedBytes = Buffer.byteLength('minyarc\0星🌙 notes/main.min\0output.ll\0', 'utf8');
  const bytes = new Uint8Array(memory.buffer);
  bytes.fill(0xa5);
  const invalid = [undefined, NaN, Infinity, -Infinity, 1.5, -2147483649,
    -1, 65533, 65535, 65536, 0xffffffff, 0x100000000];
  for (const pointer of invalid) {
    for (const [count, size] of [[pointer, 0], [0, pointer]]) {
      const before = sha256(bytes);
      assert.equal(writeArgumentSizes(memory, args, count, size), 21, 'bad WASI output pointers return EFAULT');
      assert.equal(sha256(bytes), before, 'neither output is written if either pointer is invalid');
    }
  }
  for (const invalidMemory of [undefined, null, {}, { buffer: memory.buffer }]) {
    assert.equal(writeArgumentSizes(invalidMemory, args, 0, 4), 21, 'missing or non-Wasm memory returns EFAULT');
  }
  assert.equal(writeArgumentSizes(memory, args, 65528, 65532), 0, 'the final complete u32 word is valid');
  assert.equal(new DataView(memory.buffer).getUint32(65528, true), 3);
  assert.equal(new DataView(memory.buffer).getUint32(65532, true), expectedBytes);
  assert.ok(bytes.subarray(0, 65528).every(byte => byte === 0xa5), 'successful stores affect only their output words');
  assert.equal(writeArgumentSizes(memory, [], 0, 4), 0);
  assert.equal(new DataView(memory.buffer).getUint32(0, true), 0);
  assert.equal(new DataView(memory.buffer).getUint32(4, true), 0);
  memory.grow(1);
  assert.equal(writeArgumentSizes(memory, args, 131064, 131068), 0, 'writes use the current memory buffer after growth');
  assert.equal(new DataView(memory.buffer).getUint32(131068, true), expectedBytes);
  return { name: 'WASI UTF-8 argument sizing and EFAULT boundaries', control: true,
    invalidPointerCases: invalid.length * 2, invalidMemoryCases: 4, expectedBytes };
}

async function main() {
  const evidence = path.join(root, 'build/wasm-evidence');
  await mkdir(evidence, { recursive: true });
  const report = {
    startedAt: new Date().toISOString(),
    execution: 'Actual built browser worker and LLVM frontend/backend through Node WebAssembly; no source scaffolding.',
    watchdogs: { preparationMs: 120_000, executionMs: 10_000 },
    expectedBasis: 'Literal strings, integer sums, documented module visibility/import rules, and exact source token locations.',
    tests: [],
  };
  const engine = engineClient();
  async function request(name, type, source, value) {
    const result = await engine.request(name, type, source, value);
    const row = { name, type, source, project: value ?? null,
      diagnostics: result.diagnostics, output: result.output, stdout: result.stdout, stderr: result.stderr,
      exitCode: result.exitCode, compileMs: result.compileMs, runMs: result.runMs,
      wasmBytes: result.wasm?.byteLength ?? 0,
      wasmSha256: result.wasm ? sha256(result.wasm) : null };
    report.tests.push(row);
    return { result, row };
  }
  async function run(name, value, expected, exitCode = 0) {
    const source = value.files.find(file => file.path === value.entry).source;
    const { result, row } = await request(name, 'run', source, value);
    row.expected = expected;
    row.expectedExitCode = exitCode;
    assert.deepEqual(result.diagnostics, [], `${name}: ${JSON.stringify(result.diagnostics)}`);
    assert.equal(result.exitCode, exitCode, `${name}: exit status`);
    assert.equal(result.stdout, expected, `${name}: exact stdout`);
    assert.equal(result.stderr, '', `${name}: unexpected stderr`);
    assert.equal(result.output, expected, `${name}: combined output`);
    assert.ok(result.wasm instanceof Uint8Array && WebAssembly.validate(result.wasm), `${name}: real valid module`);
    assert.ok(result.wasm.byteLength > 8, `${name}: nonempty executable`);
    console.log(`PASS ${name}: ${result.wasm.byteLength} B, status ${result.exitCode}`);
    return result;
  }
  try {
    report.tests.push(diagnosticSelectionControls());
    report.tests.push(await argumentSizeControls());
    const geometry = 'public record Point { x: Integer; y: Integer }\npublic function answer(point: Point): Integer { return point.x + point.y }\n';
    const flatEntry = 'use "./geometry.min" as geometry\nlet point: geometry.Point = geometry.Point { x: 20; y: 22 }\nprint(geometry.answer(point))\n';
    const flat = project({ 'main.min': flatEntry, 'geometry.min': geometry });
    const first = await run('relative import with public function and record', flat, '42\n');
    const reordered = { ...flat, files: [...flat.files].reverse() };
    const repeated = await run('reordered project keeps identical executable', reordered, '42\n');
    assert.equal(sha256(repeated.wasm), sha256(first.wasm));
    assert.equal(repeated.compileMs, first.compileMs, 'canonical reordered input reuses the checked program');
    const unchanged = await run('unchanged project keeps identical executable', flat, '42\n');
    assert.equal(sha256(unchanged.wasm), sha256(first.wasm));

    await run('project directories cannot collide with compiler output', project({
      'main.min': 'use "./output.ll/value.min" as first\nuse "./output-1.ll/value.min" as second\nprint(first.answer() + second.answer())\n',
      'output.ll/value.min': 'public function answer(): Integer { return 20 }\n',
      'output-1.ll/value.min': 'public function answer(): Integer { return 22 }\n',
    }), '42\n');

    const unicode = project({
      'examples/星 notes/main file.min': 'use "../../helpers/暮 geometry.min" as geometry\nlet point = geometry.Point { x: 20; y: 22 }\nprint("星: " + Text(geometry.answer(point)))\n',
      'helpers/暮 geometry.min': geometry,
    }, 'examples/星 notes/main file.min');
    await run('nested Unicode and space entry/import paths', unicode, '星: 42\n');

    const entry = 'use "./answer.min" as answer\nprint(answer.value())\n';
    await run('dependency cache seed', project({ 'main.min': entry,
      'answer.min': 'public function value(): Integer { return 40 }\n' }), '40\n');
    await run('same entry source with changed dependency', project({ 'main.min': entry,
      'answer.min': 'public function value(): Integer { return 42 }\n' }), '42\n');

    const relativeEntry = 'use "./value.min" as value\nprint(value.answer())\n';
    const entries = {
      'left/main.min': relativeEntry, 'right/main.min': relativeEntry,
      'left/value.min': 'public function answer(): Integer { return 11 }\n',
      'right/value.min': 'public function answer(): Integer { return 29 }\n',
    };
    await run('entry selection cache seed', project(entries, 'left/main.min'), '11\n');
    await run('same source and files with changed entry', project(entries, 'right/main.min'), '29\n');

    const broken = 'public function value(): Integer { return "wrong" }\n';
    const invalid = project({ 'main.min': entry, 'answer.min': broken });
    const { result: diagnostic } = await request('dependency diagnostic origin and token range', 'check', entry, invalid);
    assert.equal(diagnostic.exitCode, 1);
    assert.equal(diagnostic.output, '', 'checking does not execute an imported program');
    assert.equal(diagnostic.wasm, undefined);
    assert.equal(diagnostic.diagnostics.length, 1);
    const token = diagnostic.diagnostics[0];
    assert.equal(token.file, 'answer.min');
    assert.equal(token.line, 1);
    assert.equal(token.column, broken.indexOf('"wrong"') + 1);
    assert.equal(token.endLine, 1);
    assert.equal(token.endColumn, broken.indexOf('"wrong"') + '"wrong"'.length + 1);
    assert.equal(token.message, 'a returned value has the wrong type; expected Integer, found Text');

    const missingEntry = 'use "./missing.min" as missing\nprint(missing.answer())\n';
    const { result: missing } = await request('missing dependency rejects', 'run', missingEntry,
      project({ 'main.min': missingEntry }));
    assert.equal(missing.exitCode, 1);
    assert.equal(missing.diagnostics.length, 1);
    assert.equal(missing.diagnostics[0].file, 'missing.min');
    assert.equal(missing.diagnostics[0].message, "the file 'missing.min' could not be opened.");
    assert.deepEqual([missing.diagnostics[0].line, missing.diagnostics[0].column,
      missing.diagnostics[0].endLine, missing.diagnostics[0].endColumn], [1, 1, 1, 1]);
    assert.equal(missing.output, '');
    assert.equal(missing.wasm, undefined, 'missing input cannot retain a previous executable');
    await run('missing dependency recovery with unchanged entry', project({
      'main.min': missingEntry, 'missing.min': 'public function answer(): Integer { return 42 }\n',
    }), '42\n');

    const modules = {};
    const imports = [];
    const values = [];
    for (let number = 1; number <= 15; number++) {
      imports.push(`use "./mod${number}.min" as m${number}`);
      values.push(`m${number}.value()`);
      modules[`mod${number}.min`] = `public function value(): Integer { return ${number} }\n`;
    }
    modules['main.min'] = `${imports.join('\n')}\nprint(${values.join(' + ')})\n`;
    await run('sixteen source files import fifteen values', project(modules), '120\n');

    await run('explicit project main returns status seven', project({
      'app.min': 'function main(): Integer { print("done"); return 7 }\n',
    }, 'app.min'), 'done\n', 7);
    await run('runtime cannot see project sources or compiler outputs', project({
      'main.min': 'use "io" as io\nprint(io.fileExists("main.min"))\nprint(io.fileExists("private.min"))\nprint(io.fileExists("library/math.min"))\nprint(io.fileExists("output.ll"))\n',
      'private.min': 'public function secret(): Integer { return 42 }\n',
    }), 'false\nfalse\nfalse\nfalse\n');

    const { result: checkOnly } = await request('project check never runs entry', 'check', 'print(123)\n',
      project({ 'main.min': 'print(123)\n' }));
    assert.equal(checkOnly.exitCode, 0);
    assert.equal(checkOnly.output, '');
    assert.equal(checkOnly.wasm, undefined);
    await assert.rejects(engine.request('mismatched entry source', 'run', 'print(9)\n',
      project({ 'main.min': 'print(8)\n' })), /Source must match the project entry file/);
    report.tests.push({ name: 'mismatched entry source rejects before compilation', rejected: true });

    const { result: legacy } = await request('legacy source-only diagnostic filename', 'check', 'print(missing)\n');
    assert.equal(legacy.exitCode, 1);
    assert.equal(legacy.diagnostics[0].file, 'input.min');
    assert.equal(legacy.diagnostics[0].line, 1);
    assert.equal(legacy.diagnostics[0].column, 7);
    const { result: recovered } = await request('source-only worker recovers after project rejection', 'run', 'print(42)\n');
    assert.deepEqual(recovered.diagnostics, []);
    assert.equal(recovered.exitCode, 0);
    assert.equal(recovered.stdout, '42\n');
    assert.ok(recovered.wasm instanceof Uint8Array && WebAssembly.validate(recovered.wasm));
    report.passed = true;
    console.log(`PASS ${report.tests.length} project/worker cases with independent output and source-location oracles`);
  } catch (error) {
    report.passed = false;
    report.error = { message: error.message, stack: error.stack };
    throw error;
  } finally {
    await engine.close();
    report.finishedAt = new Date().toISOString();
    await writeFile(path.join(evidence, 'projects.json'), JSON.stringify(report, null, 2) + '\n');
  }
}

if (isMainThread) await main();
else await browserWorker();
