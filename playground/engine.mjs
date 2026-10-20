import { WASI, File, Directory, OpenFile, ConsoleStdout, PreopenDirectory } from './vendor/wasi/dist/index.js';
import { runClang } from './vendor/clang/gen/bundle.js';
import { normalizeLLVM } from './target.mjs';

const encoder = new TextEncoder();
const decoder = new TextDecoder();
export const SOURCE_LIMIT = 64 * 1024;
export const OUTPUT_LIMIT = 64 * 1024;
export const FILE_LIMIT = 16 * 1024 * 1024;
export const PATH_LIMIT = 4096;

// WASI files live in JavaScript arrays, outside WebAssembly's memory cap.
// Guard growth before allocation, including sparse writes and preallocation.
export function limitFilesystem(wasi) {
  let allocated = 0;
  let operations = 0;
  const guarded = new WeakSet();
  function guard(descriptor) {
    if (!(descriptor instanceof OpenFile) || guarded.has(descriptor)) return;
    guarded.add(descriptor);
    function reserve(end) {
      if (end < 0n || end > BigInt(FILE_LIMIT)) throw new Error('Virtual files reached the 16 MiB limit.');
      const growth = Math.max(0, Number(end) - descriptor.file.data.length);
      if (allocated + growth > FILE_LIMIT) throw new Error('Virtual files reached the 16 MiB limit.');
      allocated += growth;
    }
    for (const name of ['fd_write', 'fd_pwrite', 'fd_allocate', 'fd_filestat_set_size']) {
      const original = descriptor[name].bind(descriptor);
      descriptor[name] = (...args) => {
        const end = name === 'fd_write' ? descriptor.file_pos + BigInt(args[0].length)
          : name === 'fd_pwrite' ? args[1] + BigInt(args[0].length)
          : name === 'fd_allocate' ? args[0] + args[1] : args[0];
        reserve(end);
        return original(...args);
      };
    }
  }
  for (const descriptor of wasi.fds) guard(descriptor);
  for (const name of ['path_open', 'path_create_directory', 'path_link']) {
    const original = wasi.wasiImport[name];
    wasi.wasiImport[name] = (...args) => {
      if (++operations > 256) throw new Error('Virtual files reached the 256-operation limit.');
      const result = original(...args);
      if (name === 'path_open' && result === 0) guard(wasi.fds.at(-1));
      return result;
    };
  }
  // File names are retained host strings too. Check byte lengths before the
  // shim decodes a path, including names installed by rename/link operations.
  const pathLengths = {
    path_open: [3], path_create_directory: [2], path_link: [3, 6],
    path_rename: [2, 5], path_filestat_get: [3], path_filestat_set_times: [3],
    path_readlink: [2], path_remove_directory: [2], path_unlink_file: [2],
    path_symlink: [1, 4],
  };
  for (const [name, lengths] of Object.entries(pathLengths)) {
    const original = wasi.wasiImport[name];
    wasi.wasiImport[name] = (...args) => {
      if (lengths.some(index => !Number.isInteger(args[index]) || args[index] < 0 || args[index] > PATH_LIMIT)) {
        throw new Error('Virtual file paths must fit within 4 KiB.');
      }
      return original(...args);
    };
  }
}

function capture(limit = OUTPUT_LIMIT) {
  const parts = [];
  let length = 0;
  return {
    write(bytes) {
      if (!bytes) return;
      if (length + bytes.length > limit) throw new Error('Output reached the 64 KiB limit. Reduce the output and run again.');
      parts.push(bytes.slice());
      length += bytes.length;
    },
    text() {
      const bytes = new Uint8Array(length);
      let offset = 0;
      for (const part of parts) { bytes.set(part, offset); offset += part.length; }
      return decoder.decode(bytes);
    },
  };
}

export function parseDiagnostics(stderr) {
  const diagnostics = [];
  for (const line of stderr.split('\n')) {
    if (!line.trim()) continue;
    let diagnostic;
    try { diagnostic = JSON.parse(line); }
    catch { throw new Error(`The compiler could not finish: ${stderr.trim()}`); }
    if (diagnostic.version !== 1 || diagnostic.severity !== 'error' || typeof diagnostic.message !== 'string') {
      throw new Error('The compiler returned an unsupported diagnostic.');
    }
    diagnostics.push(diagnostic);
  }
  return diagnostics;
}

async function execute(module, args, tree = new Map()) {
  const stdout = capture();
  const stderr = capture();
  const wasi = new WASI(args, [], [
    new OpenFile(new File(new Uint8Array())),
    new ConsoleStdout(bytes => stdout.write(bytes)),
    new ConsoleStdout(bytes => stderr.write(bytes)),
    new PreopenDirectory('.', tree),
  ], { debug: false });
  limitFilesystem(wasi);
  const instance = await WebAssembly.instantiate(module, { wasi_snapshot_preview1: wasi.wasiImport });
  const exitCode = wasi.start(instance);
  return { exitCode, stdout: stdout.text(), stderr: stderr.text(), tree };
}

export async function createEngine({ loadBytes, progress = () => {} } = {}) {
  loadBytes ??= async path => {
    const response = await fetch(new URL(path, import.meta.url));
    if (!response.ok) throw new Error(`Could not load ${path} (${response.status}). Reload and try again.`);
    return new Uint8Array(await response.arrayBuffer());
  };
  progress('Loading the Minyar compiler…');
  const [frontendBytes, runtime, libraryBytes] = await Promise.all([
    loadBytes('./compiler.wasm'), loadBytes('./runtime.o'), loadBytes('./library.json'),
  ]);
  const frontend = await WebAssembly.compile(frontendBytes);
  const library = JSON.parse(decoder.decode(libraryBytes));
  let previous;

  async function check(source) {
    if (typeof source !== 'string') throw new Error('Source must be text.');
    if (encoder.encode(source).length > SOURCE_LIMIT) throw new Error('Keep your program within 64 KiB.');
    if (previous?.source === source) return previous;
    progress('Checking your program…', 'checking');
    const tree = new Map([
      ['input.min', new File(encoder.encode(source))],
      ['library', new Directory(new Map(Object.entries(library).map(([name, text]) => [name, new File(encoder.encode(text))])))],
    ]);
    const started = performance.now();
    const result = await execute(frontend, ['minyarc', 'input.min', 'output.ll', '--library', 'library', '--error-format', 'json'], tree);
    const diagnostics = parseDiagnostics(result.stderr);
    if (result.exitCode !== 0 && diagnostics.length === 0) throw new Error(`The compiler stopped with status ${result.exitCode}.`);
    const output = tree.get('output.ll');
    if (result.exitCode === 0 && (!output || diagnostics.length)) throw new Error('The compiler did not produce a complete program.');
    previous = {
      source, diagnostics, exitCode: result.exitCode,
      llvm: output ? decoder.decode(output.data) : '', compileMs: performance.now() - started,
    };
    return previous;
  }

  return {
    check,
    async request(type, source) {
      if (type !== 'check' && type !== 'run') throw new Error('Unknown playground request.');
      const checked = await check(source);
      const result = { diagnostics: checked.diagnostics, output: '', exitCode: checked.exitCode, compileMs: checked.compileMs, runMs: 0 };
      if (type === 'check' || checked.diagnostics.length) return result;
      if (!checked.wasm) {
        progress('Compiling WebAssembly…', 'compiling');
        const started = performance.now();
        const stderr = capture();
        let files;
        try {
          files = await runClang([
            'clang', '--target=wasm32-wasip1', '-O0', '-Wno-override-module', 'program.ll', 'runtime.o',
            '-Wl,-z,stack-size=8388608', '-Wl,--max-memory=268435456', '-lm', '-o', 'program.wasm',
          ], { 'program.ll': encoder.encode(normalizeLLVM(checked.llvm)), 'runtime.o': runtime }, {
            decodeASCII: false, stdout: () => {}, stderr: bytes => stderr.write(bytes),
          });
        } catch (error) {
          throw new Error(`WebAssembly compilation failed: ${stderr.text().trim() || error.message}`);
        }
        if (!(files['program.wasm'] instanceof Uint8Array)) throw new Error('LLVM did not produce WebAssembly.');
        checked.wasm = files['program.wasm'];
        checked.module = await WebAssembly.compile(checked.wasm);
        checked.backendMs = performance.now() - started;
      }
      progress('Running your program…', 'running');
      const started = performance.now();
      const execution = await execute(checked.module, ['program']);
      return {
        ...result, output: execution.stdout + execution.stderr, stdout: execution.stdout, stderr: execution.stderr,
        exitCode: execution.exitCode, wasm: checked.wasm, compileMs: checked.compileMs + checked.backendMs,
        runMs: performance.now() - started,
      };
    },
  };
}
