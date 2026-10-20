/* One Node/V8 WASI Preview 1 host for every language. All timed executions
 * instantiate the actual command module and validate the independent oracle. */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { WASI } from 'node:wasi';

const [configuration] = process.argv.slice(2);
const config = JSON.parse(fs.readFileSync(configuration, 'utf8'));
const expected = fs.readFileSync(config.oracle);
const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'minyar-wasi-compare-'));
const now = () => process.hrtime.bigint();
const elapsed = start => Number(now() - start);
const result = { node: process.versions, node_arguments: process.execArgv, platform: process.platform, arch: process.arch,
  gc_between_rounds: Boolean(global.gc), modules: {}, warmups: [], samples: [] };

async function compile(name, filename) {
  const start = now();
  const bytes = fs.readFileSync(filename);
  const load_ns = elapsed(start);
  const compileStart = now();
  const module = await WebAssembly.compile(bytes);
  const compile_ns = elapsed(compileStart);
  const imports = WebAssembly.Module.imports(module);
  assert.ok(imports.length > 0, `${name} does not import real WASI output`);
  assert.ok(imports.every(item => item.module === 'wasi_snapshot_preview1'), `${name} is not a pure WASIp1 command`);
  assert.ok(imports.some(item => item.name === 'fd_write'), `${name} does not use fd_write`);
  result.modules[name] = { load_ns, compile_ns, imports, exports: WebAssembly.Module.exports(module) };
  return module;
}

async function execute(name, module, round, position) {
  const start = now();
  const stdoutPath = path.join(directory, 'stdout');
  const stderrPath = path.join(directory, 'stderr');
  const stdout = fs.openSync(stdoutPath, 'w+');
  const stderr = fs.openSync(stderrPath, 'w+');
  try {
    const wasi = new WASI({ version: 'preview1', returnOnExit: true,
      args: ['hello'], env: {}, preopens: {}, stdout, stderr });
    const setup_ns = elapsed(start);
    const instantiateStart = now();
    const instance = await WebAssembly.instantiate(module, wasi.getImportObject());
    const instantiate_ns = elapsed(instantiateStart);
    assert.ok(instance.exports.memory instanceof WebAssembly.Memory, `${name} lacks exported memory`);
    const initial_memory_pages = instance.exports.memory.buffer.byteLength / 65536;
    let peak_memory_pages = initial_memory_pages;
    // Wasm memory cannot shrink, so final pages equal peak linear-memory pages.
    const runStart = now();
    const status = wasi.start(instance);
    const run_ns = elapsed(runStart);
    peak_memory_pages = Math.max(peak_memory_pages, instance.exports.memory.buffer.byteLength / 65536);
    const output = fs.readFileSync(stdoutPath);
    const errors = fs.readFileSync(stderrPath);
    assert.equal(status, 0, `${name} exited ${status}: ${errors}`);
    assert.deepEqual(output, expected, `${name} output differs from independent oracle`);
    assert.equal(errors.length, 0, `${name} wrote to stderr: ${errors}`);
    return { name, round, position, setup_ns, instantiate_ns, run_ns,
      ready_module_total_ns: setup_ns + instantiate_ns + run_ns,
      status, stdout_hex: output.toString('hex'), stderr_hex: errors.toString('hex'),
      initial_memory_pages, peak_memory_pages };
  } finally {
    fs.closeSync(stdout);
    fs.closeSync(stderr);
  }
}

try {
  const modules = new Map();
  for (const [name, filename] of Object.entries(config.modules)) modules.set(name, await compile(name, filename));
  const names = [...modules.keys()];
  for (let round = -config.warmups; round < config.samples; round++) {
    if (global.gc) global.gc();
    const index = ((round % names.length) + names.length) % names.length;
    const order = [...names.slice(index), ...names.slice(0, index)];
    if (Math.floor(Math.abs(round) / names.length) % 2) order.reverse();
    for (const [position, name] of order.entries()) {
      const sample = await execute(name, modules.get(name), round, position);
      (round < 0 ? result.warmups : result.samples).push(sample);
    }
  }
  process.stdout.write(JSON.stringify(result) + '\n');
} finally { fs.rmSync(directory, { recursive: true, force: true }); }
