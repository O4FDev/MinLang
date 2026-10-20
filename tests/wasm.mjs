import assert from 'node:assert/strict';
import { readFile, writeFile, mkdir, mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { resolve, join } from 'node:path';
import { spawnSync } from 'node:child_process';
import { createEngine, parseDiagnostics, SOURCE_LIMIT, FILE_LIMIT, PATH_LIMIT, limitFilesystem } from '../build/playground/engine.mjs';
import { WASI, File, OpenFile } from '../build/playground/vendor/wasi/dist/index.js';
import { tour } from '../playground/tour.mjs';
import { normalizeLLVM } from '../tools/wasm-target.mjs';
import { diagnosticSelection, sourceByteLength } from '../playground/app.mjs';

const root = resolve(new URL('..', import.meta.url).pathname);
const evidence = join(root, 'build/wasm-evidence');
await mkdir(evidence, { recursive: true });
const rows = [];
const engine = await createEngine({ loadBytes: path => readFile(new URL(path, new URL('../build/playground/engine.mjs', import.meta.url))) });
async function run(name, source, expected, exitCode = 0) {
  const result = await engine.request('run', source);
  assert.deepEqual(result.diagnostics, [], name);
  assert.equal(result.exitCode, exitCode, `${name}: status`);
  assert.equal(result.output, expected, `${name}: output`);
  assert(WebAssembly.validate(result.wasm), `${name}: valid WebAssembly`);
  rows.push({ name, compileMs: result.compileMs, runMs: result.runMs, wasmBytes: result.wasm.length });
  console.log(`PASS ${name}: ${result.wasm.length} B, compile ${result.compileMs.toFixed(1)} ms, run ${result.runMs.toFixed(1)} ms`);
  return result;
}

for (const example of tour) await run(`tour/${example.id}`, example.source, example.expected);
assert.equal(await readFile(join(root, 'examples/gallery/wasm-lanterns.min'), 'utf8'), tour.at(-1).source);

await run('integer endpoints', 'print(9223372036854775807)\nprint(-9223372036854775808)\n', '9223372036854775807\n-9223372036854775808\n');
await run('Unicode and zero bytes', 'print("星🌙" + Text(Bytes(1)) + "a")\nprint("🌙".length)\n', '星🌙\0a\n1\n');
await run('explicit entry and exit', 'function main(): Integer { print("done"); return 7 }\n', 'done\n', 7);
await run('portable math import', 'use "math" as math\nprint(math.sqrt(81.0))\n', '9.0\n');
await run('virtual file round trip', 'use "io" as io\nio.writeTextFile("hello.txt", "星")\nprint(io.readTextFile("hello.txt"))\n', '星\n');
await run('callback ownership', 'let offset = 2\nlet apply: (Integer) -> Integer = function(value) { return value + offset }\nprint(apply(40))\n', '42\n');
await run('runtime stop', 'fail("The harbour has no light.")\n', 'Minyar stopped: The harbour has no light.\n', 1);

const invalid = await engine.request('check', 'let stars: Integer = "many"\nprint(stars)\n');
assert.equal(invalid.exitCode, 1);
assert.equal(invalid.diagnostics.length, 1);
assert.equal(invalid.diagnostics[0].file, 'input.min');
assert.equal(invalid.diagnostics[0].line, 1);
assert.equal(invalid.diagnostics[0].column, 5);
assert.match(invalid.diagnostics[0].message, /expected Integer, found Text/);
assert.equal(invalid.wasm, undefined);
const recovery = await engine.request('check', 'function first(): Integer { return "one" }\nfunction second(): Boolean { return 2 }\n');
assert.equal(recovery.diagnostics.length, 2, 'real WASI setjmp recovery reports independent errors');
assert.deepEqual(recovery.diagnostics.map(diagnostic => diagnostic.line), [1, 2]);
await run('success after rejection', 'print(42)\n', '42\n');
const checkOnly = await engine.request('check', 'print(999)\n');
assert.equal(checkOnly.output, '');
assert.equal(checkOnly.wasm, undefined, 'live checking never executes source');
await assert.rejects(engine.request('check', ' '.repeat(SOURCE_LIMIT + 1)), /64 KiB/);
await assert.rejects(engine.request('check', 42), /Source must be text/);
await assert.rejects(engine.request('anything', ''), /Unknown playground request/);
await assert.rejects(engine.request('run', 'for index in 0..10000 { print("many lines of output") }\n'), /Output reached/);
await assert.rejects(engine.request('run', 'use "io" as io\nlet chunk = Text(Bytes(1048576))\nfor index in 0..20 { io.writeTextFile(Text(index), chunk) }\n'), /Virtual files reached/);
await assert.rejects(engine.request('run', 'use "io" as io\nfor index in 0..257 { io.writeTextFile(Text(index), "") }\n'), /256-operation limit/);
await assert.rejects(engine.request('run', 'use "io" as io\nlet name = "a"\nfor index in 0..13 { name += name }\nio.writeTextFile(name, "")\n'), /4 KiB/);
await run('recovery after resource limits', 'print("ready again")\n', 'ready again\n');
await run('virtual files reset', 'use "io" as io\nprint(io.fileExists("hello.txt"))\nio.writeTextFile("hello.txt", "kept only here")\n', 'false\n');
await run('cached program files reset', 'use "io" as io\nprint(io.fileExists("hello.txt"))\nio.writeTextFile("hello.txt", "kept only here")\n', 'false\n');
const globalSource = 'global values: List<Integer> = [1]\nvalues.add(2)\nprint(values.length)\n';
await run('global state starts fresh', globalSource, '2\n');
await run('cached global state starts fresh', globalSource, '2\n');
// Sparse writes/allocate/truncate must reject before the shim allocates host memory.
for (const operation of ['fd_pwrite', 'fd_allocate', 'fd_filestat_set_size']) {
  const file = new File(new Uint8Array());
  const descriptor = new OpenFile(file);
  const wasi = new WASI([], [], [descriptor], { debug: false });
  limitFilesystem(wasi);
  assert.throws(() => operation === 'fd_pwrite' ? descriptor[operation](new Uint8Array([1]), BigInt(FILE_LIMIT))
    : operation === 'fd_allocate' ? descriptor[operation](BigInt(FILE_LIMIT), 1n)
    : descriptor[operation](BigInt(FILE_LIMIT) + 1n), /Virtual files reached/);
  assert.equal(file.data.length, 0, `${operation} allocated before quota rejection`);
}
// Reject metadata growth before UTF-8 decoding, even if no memory is present.
for (const [operation, lengths] of Object.entries({ path_open: [3], path_create_directory: [2], path_link: [3, 6], path_rename: [2, 5] })) {
  for (const index of lengths) {
    const wasi = new WASI([], [], [], { debug: false });
    limitFilesystem(wasi);
    const args = Array(9).fill(0);
    args[index] = PATH_LIMIT + 1;
    assert.throws(() => wasi.wasiImport[operation](...args), /4 KiB/);
  }
}
assert.throws(() => parseDiagnostics('not JSON'), /could not finish/);
assert.equal(sourceByteLength('🌙'), 4);
assert.deepEqual(diagnosticSelection('🌙abc\nhello', 1, 2, 1, 4), { start: 2, end: 4 });

// Same source, same frontend: compare real wasm compiler output with native.
const source = 'function double(n: Integer): Integer { return n * 2 }\nprint(double(21))\n';
const wasmFrontend = await engine.check(source);
const work = await mkdtemp(join(tmpdir(), 'minyar-wasm-parity-'));
try {
  await writeFile(join(work, 'input.min'), source);
  const native = spawnSync(join(root, 'build/minyarc'), ['input.min', 'output.ll', '--library', join(root, 'library'), '--error-format', 'json'], { cwd: work, encoding: 'utf8', timeout: 120000 });
  assert.equal(native.status, 0, native.stderr);
  assert.equal(normalizeLLVM(wasmFrontend.llvm), normalizeLLVM(await readFile(join(work, 'output.ll'), 'utf8')), 'wasm/native frontend LLVM parity');
} finally { await rm(work, { recursive: true, force: true }); }

await writeFile(join(evidence, 'engine.json'), JSON.stringify({ tests: rows, compilerBytes: (await readFile(join(root, 'build/wasm/compiler.wasm'))).length }, null, 2) + '\n');
console.log(`PASS ${rows.length} executable browser-engine cases; diagnostics, recovery, isolation limits and native LLVM parity`);
