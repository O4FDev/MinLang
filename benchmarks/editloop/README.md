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
