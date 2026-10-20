/* Minyar's frontend emits portable LLVM with 64-bit language values. Native
 * stack-trace tables use linker-relative relocations unavailable in wasm.
 * Remove only that optional metadata; runtime failure messages stay intact.
 * This module is also imported unchanged by the static browser worker. */
export function normalizeLLVM(llvm) {
  if (typeof llvm !== 'string') throw new TypeError('LLVM input must be text');
  return llvm.split('\n').filter(line =>
    !/^target (?:triple|datalayout)\s*=/.test(line) &&
    !/^@"minyar\.trace\|/.test(line) &&
    !/^@minyar_trace_(?:modules|module_count)\s*=/.test(line)
  ).join('\n').replace(/"(?:target-cpu|target-features|tune-cpu)"="[^"]*"\s*/g, '')
    .replace(/^define i32 @main\(/m, 'define i32 @minyar_wasm_main(');
}

if (typeof process !== 'undefined' && process.versions?.node &&
    import.meta.url === (await import('node:url')).pathToFileURL(process.argv[1] ?? '').href) {
  const fs = await import('node:fs/promises');
  const path = await import('node:path');
  const { fileURLToPath } = await import('node:url');
  const { spawnSync } = await import('node:child_process');
  const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
  const args = process.argv.slice(2);
  try {
    if (args[0] === '--normalize' && args.length === 3) {
      await fs.writeFile(args[2], normalizeLLVM(await fs.readFile(args[1], 'utf8')));
    } else if ((args.length === 2 || args.length === 3) && !args[0].startsWith('-') &&
               (args[2] === undefined || /^-O[02]$/.test(args[2]))) {
      const source = path.resolve(args[0]);
      const output = path.resolve(args[1]);
      const sysroot = path.resolve(process.env.WASM_SYSROOT ?? path.join(root, 'build/wasm/sysroot'));
      const runtime = path.resolve(process.env.MINYAR_WASM_RUNTIME ?? path.join(root, 'build/wasm/runtime.o'));
      const compiler = process.env.MINYAR_COMPILER ?? path.join(root, 'build/minyarc');
      let clang = process.env.LLVM_CC;
      if (!clang) {
        const selected = spawnSync('sh', [path.join(root, 'tools/toolchain.sh'), 'default-clang'], { encoding: 'utf8' });
        if (selected.error || selected.status !== 0) throw new Error('cannot select the LLVM compiler');
        clang = selected.stdout.trim();
      }
      for (const file of [runtime, path.join(sysroot, 'lib/wasm32-wasip1/libc.a')]) {
        try { await fs.access(file); } catch { throw new Error('WASI tools are missing; run make prepare-wasm build/wasm/runtime.o first'); }
      }
      await fs.mkdir(path.dirname(output), { recursive: true });
      const work = await fs.mkdtemp(path.join(path.dirname(output), '.minyar-wasm-'));
      const run = (program, arguments_) => {
        const result = spawnSync(program, arguments_, { stdio: 'inherit', timeout: 120000 });
        if (result.error) throw result.error;
        if (result.status !== 0) {
          process.exitCode = result.status ?? 1;
          return false;
        }
        return true;
      };
      try {
        const llvm = path.join(work, 'program.ll');
        const lowered = path.join(work, 'program-wasm.ll');
        const wasm = path.join(work, 'program.wasm');
        if (run(compiler, [source, llvm, '--library', path.join(root, 'library')])) {
          await fs.writeFile(lowered, normalizeLLVM(await fs.readFile(llvm, 'utf8')));
          if (run(clang, ['--target=wasm32-wasip1', `--sysroot=${sysroot}`, `-resource-dir=${sysroot}`,
            '-Wno-override-module', args[2] ?? '-O2', '-mllvm', '-wasm-enable-sjlj',
            '-mllvm', '-wasm-use-legacy-eh=false', '-Wl,--stack-first', '-Wl,-z,stack-size=8388608',
            '-Wl,--max-memory=536870912', lowered, runtime, '-lm', '-lsetjmp', '-o', wasm])) {
            await fs.rename(wasm, output);
          }
        }
      } finally { await fs.rm(work, { recursive: true, force: true }); }
    } else {
      console.error('usage: node tools/wasm-target.mjs SOURCE.min OUTPUT.wasm [-O0|-O2]\n' +
        '       node tools/wasm-target.mjs --normalize INPUT.ll OUTPUT.ll');
      process.exitCode = 2;
    }
  } catch (error) {
    console.error(`wasm-target: ${error.message}`);
    process.exitCode = 1;
  }
}
