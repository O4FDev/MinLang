# WASI hello-world: size and startup

On 20 October 2026, these four programs printed exactly `Hello, world!` followed
by one LF using the same Node/V8 WASI Preview 1 host. Minyar produced the smallest
binary in this run. Rust had lower startup latency and a smaller linear-memory
allocation. This measures hello-world startup, not general language performance.

The [raw evidence](../../benchmarks/wasm/results-20261020.json) contains every
sample, warmup, source text, source and binary SHA256, compiler command,
toolchain version, import/export list and memory measurement. The
[runner](../../tools/wasm-compare.py) reproduces the experiment.

## Sources and toolchains

| Language | Version / target | Real output operation |
| --- | --- | --- |
| [Minyar source](../../benchmarks/wasm/hello.min) | `5119d6779d9f5575c809b79e330dfcefa7c09c94`, LLVM 23.1.2, `wasm32-wasip1` | `print`, using the ordinary Text runtime and libc stdout |
| [Go source](../../benchmarks/wasm/hello.go) | Go 1.27.2, `GOOS=wasip1 GOARCH=wasm` | `fmt.Println` |
| [Rust source](../../benchmarks/wasm/hello.rs) | Rust 1.99.1, LLVM 23.1.1, `wasm32-wasip1` | `println!` |
| [Zig source](../../benchmarks/wasm/hello.zig) | Zig 0.17.0, `wasm32-wasi` | `std.Io.File.stdout().writeStreamingAll` with `std.process.Init` |

All use their real runtime and standard output APIs. These APIs carry different
formatting, initialization and failure behavior; matching their output does not
make their library implementations identical. There is no TinyGo, custom tiny
runtime, dummy export, `js/wasm` fallback, or replacement handwritten Wasm.

Go's WASIp1 port and its ordinary `fmt.Println` build recipe are described in the
[Go WASI documentation](https://go.dev/blog/wasi). Rust documents its
[`wasm32-wasip1` target](https://doc.rust-lang.org/stable/rustc/platform-support/wasm32-wasip1.html).
Zig's stdout operation follows its
[0.17.0 hello-world example](https://ziglang.org/documentation/0.17.0/#Hello-World).

The box initially provided Go 1.23.4 and Rust 1.97.1 without a WASI standard
library; Zig was absent. The comparison instead uses isolated official
toolchains pinned from the live [Go](https://go.dev/dl/?mode=json),
[Rust](https://static.rust-lang.org/dist/channel-rust-stable.toml), and
[Zig](https://ziglang.org/download/index.json) manifests. The exact archive URLs
and SHA256 values are in [toolchains.json](../../benchmarks/wasm/toolchains.json).
No global installation is changed. Installation and download time are excluded.

## Binary sizes

These are complete command modules, excluding the common host. Compiler-native
debug stripping is followed by the same metadata-only operation for every
language: remove custom sections, preserving every standard section byte for
byte. No optimizer rewrites the executable sections. Every final module imports
real `fd_write`, imports only `wasi_snapshot_preview1`, exports memory, exits zero
and matches the independently stored [14-byte oracle](../../benchmarks/wasm/expected.txt).

| Language | Compiler output bytes | Delivered uncompressed bytes | Gzip level 9 bytes |
| --- | ---: | ---: | ---: |
| Minyar | 31,311 | 29,480 | 11,979 |
| Go | 2,426,446 | 2,426,369 | 700,982 |
| Rust | 38,530 | 38,530 | 15,652 |
| Zig | 61,996 | 61,996 | 20,579 |

Gzip uses level 9 and a zero timestamp, without a filename. Each language's eight
source rebuilds produced the same delivered binary SHA256:

```text
Minyar bb08341681b590632795dc1a5abb9e47a3622a5087721e0f8321fe8be87b09c1
Go     06ea34bf348bb0c4dc668fb9a5732b7ea3e3135307d5ef45ce69c036f23c781b
Rust   4dcf2a2dadaf958d77a93f4d67e4259fc5c0e9c9a818a8e3473f5f7cab49c0f5
Zig    8058872299e795ccccf0877ce683cca2f82259ecf76f30d226c89d45562697fe
```

## Source-to-module build time

Release recipes are Minyar `-O2`; Go's normal optimization with
`-trimpath -ldflags="-s -w -buildid="`; Rust `opt-level=3`, fat LTO, one codegen
unit, `panic=abort`, no debuginfo and `strip=symbols`; Zig `ReleaseFast -fstrip`.
The flags are intentionally reported rather than described as equivalent.
Minyar's exact link flags and runtime object hash are saved with the driver
source in the raw evidence.

The first build starts with empty private Go/Zig dependency caches. Seven later
builds reuse dependencies, delete the output and append a distinct source
comment to invalidate the application source cache. Commands alternate in a
rotated and reversed order. The comment does not change observable behavior or
the final binary hash.

| Language | First private-cache build ms | Warm best ms | Warm median ms | Warm p95 ms |
| --- | ---: | ---: | ---: | ---: |
| Minyar | 39.7 | 39.136 | 40.810 | 43.943 |
| Go | 1,356.3 | 51.623 | 56.044 | 61.350 |
| Rust | 169.7 | 167.931 | 171.012 | 177.429 |
| Zig | 2,383.7 | 724.862 | 737.470 | 750.207 |

These are source-to-module command timings, including process startup and
linking. They are not isolated frontend throughput: Minyar's compiler/runtime
and Rust's target standard library are prebuilt, while Go/Zig may compile
standard-library dependencies during first use. Dependency caching and compiler
pipelines differ. Common metadata stripping and gzip run after these timers.

## Fresh-engine startup

Each of 12 samples per language launches a fresh Node 24.18.1 process with the
same V8 engine and `node:wasi` Preview 1 implementation. It reads the file,
calls `WebAssembly.compile`, creates the WASI context, instantiates the module,
then calls `wasi.start`. Each phase has its own wall timer. Whole-process timing
also includes Node startup, loading the harness and checking the output.

All times below are milliseconds. Phase columns are medians. Whole process is
best / median / p95.

| Language | File read | Engine compile | Context setup | Instantiate | Start | Whole process |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Minyar | 0.025 | 0.259 | 0.257 | 0.785 | 0.398 | 25.477 / 27.726 / 30.375 |
| Go | 0.672 | 2.433 | 0.251 | 1.596 | 6.821 | 35.510 / 36.970 / 39.870 |
| Rust | 0.031 | 0.248 | 0.245 | 0.574 | 0.379 | 24.726 / 27.000 / 31.166 |
| Zig | 0.038 | 0.303 | 0.255 | 1.515 | 0.618 | 26.071 / 28.172 / 31.943 |

“Fresh engine” does not mean a cold disk or network cache. The OS page cache was
not flushed. `WebAssembly.compile` measures that API call, not every possible
later optimizing compiler task. The small program makes host and runtime
startup the dominant work.

## Warm module, fresh instance

The warm experiment compiles each module once, performs 20 warmups per language,
then records 200 samples per language in one Node process. Every sample creates
a fresh WASI context and fresh instance of the same precompiled module. The
language order rotates and reverses; explicit host GC runs between rounds,
outside all phase timers.

Context setup includes opening the common stdout/stderr capture files and
constructing WASI. Start includes the actual guest output syscall. Oracle reads,
assertions and closing capture files are outside those phase timers. Each sample
must exit zero, emit exactly the oracle bytes and leave stderr empty.

| Language | Setup median µs | Instantiate median µs | Start median µs | Setup + instantiate + start ms, best / median / p95 |
| --- | ---: | ---: | ---: | ---: |
| Minyar | 58.735 | 367.676 | 30.542 | 0.296 / 0.451 / 0.616 |
| Go | 53.315 | 1,936.430 | 341.076 | 1.434 / 2.322 / 3.000 |
| Rust | 58.325 | 173.922 | 23.148 | 0.210 / 0.257 / 0.417 |
| Zig | 54.362 | 977.957 | 38.793 | 0.929 / 1.074 / 1.618 |

The raw file retains best, median and p95 for every phase, not just the combined
timer. The p95 is nearest-rank `ceil(0.95 * n)`; with seven build samples or 12
cold samples it is the maximum. These small sample counts do not establish
confidence bounds. No outliers were removed.

## Linear memory

One page is 65,536 bytes. Initial pages are measured immediately after
instantiation; peak pages are measured after start. WebAssembly linear memory
cannot shrink, so final pages are the peak page count. The values were constant
across the 200 warm samples. They are not process RSS or committed physical RAM.

| Language | Initial pages | Peak pages | Peak MiB |
| --- | ---: | ---: | ---: |
| Minyar | 129 | 129 | 8.063 |
| Go | 36 | 45 | 2.813 |
| Rust | 17 | 17 | 1.063 |
| Zig | 257 | 258 | 16.125 |

Minyar's configured 8 MiB stack costs more initial linear address space than the
Rust or Go recipes here. Only Minyar's recipe declares a 512 MiB maximum; the
other modules do not declare an explicit maximum. Stack/heap policies and host
memory management differ, so binary size alone is not a memory comparison.

## Reproduction and scope

The measured host was Linux x86_64, glibc 2.39, eight available vCPUs on an AMD
Ryzen 9 9950X host. Node was 24.18.1. The complete version output, engine version,
affinity, archive hashes and executable hashes are recorded in the JSON.

On a Linux x86_64 build machine with Python 3.12 or later:

```sh
make -j8 build/minyarc build/wasm/runtime.o
python3 tools/wasm-compare.py --prepare-toolchains \
  --revision "$(git rev-parse HEAD)" \
  --build-samples 7 --cold-samples 12 --warmups 20 --samples 200
```

The default output is `build/wasm-compare/results.json`; its companion files
contain raw command modules, gzip files and each host run. The runner clears
only its private dependency-cache directory between invocations and retains
verified toolchain downloads. Commands and downloads have explicit timeouts.
For this recorded run, every build and execution used the leased remote Boat
box; no build or benchmark ran on the laptop.

There were 48 fresh-engine executions, 80 warmups and 800 measured warm
executions, all verified. Conclusions apply to these sources, toolchains,
release flags, standard-library APIs and host. Larger workloads, dynamic
allocation, callbacks, browser network delivery, long-running computation and
other Wasm engines require their own measurements.
