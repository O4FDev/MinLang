# Edit-to-observation time

`run.py` edits the reply text of a small HTTP service five times and measures
until a client sees the new text. Minyar runs `benchmarks/livepatch/server`
under `minyar run --watch` with and without `--hot`; Rust (`../connections/rust`,
debug, incremental) and Go (`../connections/server.go`) rebuild and restart as
cargo-watch or a shell loop would.

Measured 2026-10-25, 4-vCPU Boat box (Linux 6.8 VM), median (min–max) seconds:

| variant | seconds | process state kept |
| --- | --- | --- |
| Minyar `--watch --hot`, whole-program update images | 0.569 (0.427–0.728) | yes |
| Minyar `--watch --hot`, changed-function images | 0.311 (0.304–0.365) | yes |
| Minyar `--watch` | 1.435 (1.412–1.516) | no |
| Rust `cargo build` + restart | 0.224 (0.191–0.343) | no |
| Go `go build` + restart | 0.268 (0.259–0.317) | no |

With changed-function images the hot loop is within 1.2–1.4x of Rust's and
Go's rebuild-and-restart for this small service and keeps the process state;
plain watch mode is 4.5–5.6x slower.

After hot builds stopped re-running the launcher's toolchain checks per edit
(two later rounds of seven edits, same box): Minyar `--watch --hot` 0.237 s and
0.210 s, Rust 0.153 s and 0.159 s, Go 0.200 s and 0.182 s. About 0.12 s of the
Minyar figure is the watcher's deliberate save debounce; the Rust and Go loops
here have none.

Plain `--watch`, 2026-10-26 (8-vCPU box, seven edits, two alternating rounds
per tree): 1.15–1.20 s before → 0.24–0.27 s after, with `minyar --watch --hot`
at 0.22–0.24 s in the same sessions. Without `MINYAR_CLANG` in the environment
the plain loop was 0.46–0.49 s before. Three changes: the launcher caches a
configured runtime instead of compiling it on every build (0.75 s whenever a
Clang is selected with `MINYAR_CLANG`), a watch session's rebuilds skip the
launcher's toolchain check after its first build, and watch rebuilds link
cached partitions (`tools/link-partitions.min`), so an edit recompiles one or
two partition objects. `timeline.py` shows where one rebuild spends its time.
On neo-db (41.7 MB of LLVM) a plain debug rebuild after a one-line edit drops
from 7.8–8.4 s to 2.3–2.8 s with the partitioned link (4-vCPU box).
