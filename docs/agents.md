# Writing Minyar with a coding agent

A short page for people and agents who already program in Rust, C, Go, Swift
or Zig and want working systems code in few turns. Everything here is in the
longer guides; this page puts the loop and the surprises in one place.

## The loop

```sh
minyar new service && cd service   # or write Minyar.toml by hand
minyar --check src/main.min        # types and modules, no linking: well under a second
minyar check --error-format json   # one JSON object per error: code, span, help
minyar explain E0207               # the family behind an error code, with a valid example
minyar doc files                   # a standard module's public signatures
minyar doc files.openFile          # one declaration with its documentation
minyar doc spawn                   # search every standard module's public names
minyar test                        # test blocks beside the code, then tests/*.min programs
minyar sim                         # deterministic universes in sim/*.min
```

Every compiler error carries a `help` line with a concrete repair. When it
names a spelling from another language (`fn`, `struct`, `u64`, `Vec`, `-> T`,
`let mut`, `x?`, `.len()`), the help gives the Minyar form; the
[Rust table](from-rust.md#spellings-at-a-glance) lists them together.

## Shapes that differ from Rust and Swift

- A `match` that produces a value holds exactly one expression per arm; an arm
  cannot `return`. Leave early from one case as a statement first:

  ```minyar
  function port(text: Text): Result<Integer, Text> {
      if text == "" { return Err("no port") }
      return Ok(8080)
  }

  function main(): Integer {
      let parsed = port("8080")
      if parsed is Err(problem) {
          print(problem)
          return 1
      }
      print(parsed.unwrap())
      return 0
  }
  ```

- `if` is a statement. Choose a value with `match condition { true { a } false { b } }`.
- `try expression` propagates a Result error (prefix, not `?`); the error types
  must match. A Result cannot be ignored: handle it, `try` it, `unwrap()` it or
  write `let _ = ...`.
- Every module is imported by name: `use "files" as files`, `use "text" as text`.
- Records, Lists, Maps and Bytes are shared references; there is no `&` or `mut`.
- `expect(condition)` works inside `test "name" { ... }` blocks; a `tests/*.min`
  program reports failure with `fail("...")` or a nonzero exit.

## Systems pieces worth knowing

- Binary layouts: [C-layout records](language.md#c-layout-records) with
  `cView` over Bytes, `sizeOf` and `offsetOf`; Bytes has `getUInt32`-style accessors.
- Storage: write the engine against `disk.Disk`, run it on `disk.host()`, and
  crash-test it on `disk.simulated(world)` under `minyar sim`
  ([one storage engine, two disks](simulation.md#one-storage-engine-two-disks);
  complete example: [examples/kvstore](../examples/kvstore)).
- Real-process crash tests: start a worker with `workers.startSelf(mode)`;
  `Worker.close()` kills it with SIGKILL.
- Kernels: the same source runs hosted and under QEMU through
  `tools/osdev.py test --kernel-source FILE`
  ([kernel development](os-development.md); starter:
  [examples/kernel/frames-kernel.min](../examples/kernel/frames-kernel.min)).
