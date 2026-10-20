import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { readFileSync, writeFileSync, mkdirSync, readdirSync } from 'node:fs';
import path from 'node:path';
import { WASI } from 'node:wasi';
import { normalizeLLVM } from '../tools/wasm-target.mjs';

if (process.argv[2] === '--run') {
  const file = path.resolve(process.argv[3]);
  const wasi = new WASI({ version: 'preview1', returnOnExit: true,
    args: ['minyar', ...process.argv.slice(4)], env: {},
    preopens: { '.': path.dirname(file), '/sandbox': path.dirname(file) } });
  const module = await WebAssembly.compile(readFileSync(file));
  const instance = await WebAssembly.instantiate(module, wasi.getImportObject());
  process.exitCode = wasi.start(instance);
} else {
  const directory = 'build/wasm/target-tests';
  const sysroot = process.env.WASM_SYSROOT ?? 'build/wasm/sysroot';
  const compiler = process.env.MINYAR_COMPILER ?? './build/minyarc';
  const clang = process.env.LLVM_CC ?? 'clang';
  const runtime = process.env.MINYAR_WASM_RUNTIME ?? 'build/wasm/runtime.o';
  const builtins = `${sysroot}/lib/wasm32-unknown-wasip1/libclang_rt.builtins.a`;
  mkdirSync(directory, { recursive: true });

  function command(program, args, timeout = 60000) {
    const result = spawnSync(program, args, { encoding: 'utf8', timeout, maxBuffer: 8 * 1024 * 1024 });
    assert.ifError(result.error);
    assert.equal(result.signal, null, `${program} terminated by ${result.signal}`);
    return result;
  }

  const cases = [
    ['numbers', `function factorial(n: Integer): Integer {
      if n <= 1 { return 1 }; return n * factorial(n - 1)
    }
    print(9223372036854775807); print(-9223372036854775808)
    print(wrappingAdd(9223372036854775807, 1)); print(factorial(10))
    print(0.1 + 0.2); print(Integer(-7.9)); print(1 << 40)
    print(false && factorial(1) == 0); print(true || factorial(1) == 0)
    `, '9223372036854775807\n-9223372036854775808\n-9223372036854775808\n3628800\n0.30000000000000004\n-7\n1099511627776\nfalse\ntrue\n'],
    ['unicode', `let word = "hé🚀llo"
    print(word.length); print(word.byteLength); print(word[1]); print(word[2])
    print(word.slice(1, 4)); print("Hello, \\(word)!")
    let wire = Bytes(word); print(wire.length); print(Text(wire))
    `, '6\n10\né\n🚀\né🚀l\nHello, hé🚀llo!\n10\nhé🚀llo\n'],
    ['lists-records', `record Box { label: Text; values: List<Integer> }
    let box = Box { label: "night"; values: [20, 21] }
    let alias = box; alias.label += " sky"; alias.values.add(22)
    box.values[0] += 1
    print(box.label); print(box.values.length)
    for value in box.values { print(value) }
    let nested: List<List<Integer>> = [[1, 2], [], [3]]
    print(nested[0][1]); print(nested[1].length)
    `, 'night sky\n3\n21\n21\n22\n2\n0\n'],
    ['generics-choice', `record Pair<First, Second> { first: First; second: Second }
    function firstOr<Item>(values: List<Item>, fallback: Item): Item {
      if values.length == 0 { return fallback }; return values[0]
    }
    choice Signal { Note(message: Text); Quiet }
    function describe(signal: Signal): Text {
      match signal { Note(message) { return message }; Quiet { return "quiet" } }
    }
    let pair = Pair<Text, Integer> { first: firstOr([], "kept"); second: 42 }
    print(pair.first); print(pair.second); print(describe(Note("sing"))); print(describe(Quiet))
    `, 'kept\n42\nsing\nquiet\n'],
    ['map-set', `let scores: Map<Text, Integer> = Map()
    scores["Ada"] = 40; scores["Ada"] += 2
    print(scores["Ada"]); print(scores.length)
    let names: Set<Text> = Set(); names.add("Ada"); names.add("Ada"); names.add("Minyar")
    print(names.length); print(names.contains("Ada")); print(names.remove("Ada"))
    print(names.contains("Ada"))
    `, '42\n1\n2\ntrue\ntrue\nfalse\n'],
    ['bytes', `let bytes = Bytes()
    bytes.addInt64(9223372036854775807); bytes.addFloat64(3.5)
    print(bytes.getInt64(0)); print(bytes.getFloat64(8))
    bytes.resize(20); print(bytes[19]); bytes[19] = 255; print(bytes[19])
    print(bytes.slice(16, 20).length)
    `, '9223372036854775807\n3.5\n0\n255\n4\n'],
    ['callbacks-cycles', `record State { value: Text; callbacks: List<Callback<Text, Text>> }
    function make(): Callback<Text, Text> {
      let state = State { value: "kept"; callbacks: [] }
      let callback = function(suffix: Text): Text { return state.value + suffix }
      state.callbacks.add(callback)
      return state.callbacks[0]
    }
    let callback = make(); print(callback(" alive")); print(callback(" twice"))
    `, 'kept alive\nkept twice\n'],
    ['library', `use "math" as math
    use "random" as random
    use "io" as io
    print(math.sqrt(49.0)); print(random.bytes(16).length)
    io.writeTextFile("/sandbox/message.txt", "a little light 🚀")
    print(io.readTextFile("/sandbox/message.txt"))
    `, '7.0\n16\na little light 🚀\n'],
    ['overflow', 'let value = 9223372036854775807\nprint(value + 1)\n', '', 1, 'Integer calculation is outside the supported range'],
    ['bounds', 'let values = [1, 2]\nprint(values[3])\n', '', 1, 'List position'],
    ['huge-bytes', 'print(Bytes(4294967296).length)\n', '', 1, 'Bytes are too large'],
    ['recursion', 'function forever(n: Integer): Integer { return forever(n + 1) + n }\nprint(forever(0))\n', '', 1, 'maximum call depth'],
    ['ownership', `function watch() { native "wasmtest" }
    record Node { name: Text; links: List<Node>; callbacks: List<Callback<Text, Text>> }
    function garden() {
      let node = Node { name: "a little light"; links: []; callbacks: [] }
      node.links.add(node)
      node.callbacks.add(function(suffix: Text): Text { return node.name + suffix })
      let callback = node.callbacks[0]
      let result = callback(" 🚀")
      if result != "a little light 🚀" { fail("the callback lost its owner") }
    }
    watch()
    for index in 0..100 { garden() }
    print("cycles released")
    `, 'cycles released\nWASI ownership: no live managed objects\n'],
  ];

  // Run the same feature-indexed sources and independent stdout oracles as
  // the native language gate, without rewriting their programs or expected data.
  mkdirSync(`${directory}/build`, { recursive: true });
  for (const entry of readdirSync('tests/conformance', { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
    if (!entry.isDirectory()) continue;
    const fixture = `tests/conformance/${entry.name}`;
    cases.push([`conformance-${entry.name}`, readFileSync(`${fixture}/program.min`, 'utf8'),
      readFileSync(`${fixture}/expected.stdout`, 'utf8')]);
  }

  const ownershipRuntime = `${directory}/ownership-runtime.o`;
  const instrumented = command(clang, ['--target=wasm32-wasip1', `--sysroot=${sysroot}`,
    `-resource-dir=${sysroot}`, '-O2', '-mllvm', '-wasm-enable-sjlj',
    '-mllvm', '-wasm-use-legacy-eh=false', '-c', 'tests/wasm-ownership.c', '-o', ownershipRuntime]);
  assert.equal(instrumented.status, 0, instrumented.stderr);

  let executions = 0;
  for (const [name, source, stdout, exit = 0, error = ''] of cases) {
    const input = `${directory}/${name}.min`;
    const llvm = `${directory}/${name}.ll`;
    const lowered = `${directory}/${name}-wasm.ll`;
    writeFileSync(input, source);
    const compiled = command(compiler, [input, llvm, '--library', 'library']);
    assert.equal(compiled.status, 0, `${name}: ${compiled.stderr}`);
    writeFileSync(lowered, normalizeLLVM(readFileSync(llvm, 'utf8')));
    for (const optimization of ['0', '2']) {
      const wasm = `${directory}/${name}-O${optimization}.wasm`;
      const linked = command(clang, ['--target=wasm32-wasip1', `--sysroot=${sysroot}`,
        `-resource-dir=${sysroot}`, '-O' + optimization, '-Wno-override-module',
        '-mllvm', '-wasm-enable-sjlj', '-mllvm', '-wasm-use-legacy-eh=false',
        '-Wl,--stack-first', '-Wl,-z,stack-size=8388608',
        lowered, name === 'ownership' ? ownershipRuntime : runtime, builtins, '-lsetjmp', '-lm', '-o', wasm]);
      assert.equal(linked.status, 0, `${name} O${optimization}: ${linked.stderr}`);
      const result = command(process.execPath, ['--no-warnings', import.meta.filename, '--run', wasm], 15000);
      assert.equal(result.status, exit, `${name} O${optimization}: ${result.stderr}`);
      assert.equal(result.stdout, stdout, `${name} O${optimization} output`);
      if (error) assert.ok(result.stderr.includes(error), `${name}: ${result.stderr}`);
      else assert.equal(result.stderr, '', `${name} O${optimization} stderr`);
      executions++;
    }
  }
  const cliSource = `${directory}/source with spaces.min`;
  const cliOutput = `${directory}/output with spaces.wasm`;
  writeFileSync(cliSource, 'print("compiled from a file")\n');
  for (const optimization of ['-O0', '-O2']) {
    const compiled = command(process.execPath, ['tools/wasm-target.mjs', cliSource, cliOutput, optimization]);
    assert.equal(compiled.status, 0, compiled.stderr);
    const result = command(process.execPath, ['--no-warnings', import.meta.filename, '--run', cliOutput]);
    assert.equal(result.status, 0, result.stderr);
    assert.equal(result.stdout, 'compiled from a file\n');
    executions++;
  }
  const original = readFileSync(cliOutput);
  writeFileSync(cliSource, 'let value: Integer = "a type error"\n');
  const rejected = command(process.execPath, ['tools/wasm-target.mjs', cliSource, cliOutput]);
  assert.equal(rejected.status, 1, rejected.stderr);
  assert.ok(rejected.stderr.includes('Integer'), rejected.stderr);
  assert.deepEqual(readFileSync(cliOutput), original, 'a failed compile replaced the previous wasm output');
  console.log(`WASI target: ${executions} executions passed at O0/O2; CLI rejection preserves output`);
}
