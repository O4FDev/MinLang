# Edit-to-observation time

`run.py` edits the reply text of a small HTTP service five times and measures
until a client sees the new text. Minyar runs `benchmarks/livepatch/server`
under `minyar run --watch` with and without `--hot`; Rust (`../connections/rust`,
debug, incremental) and Go (`../connections/server.go`) rebuild and restart as
cargo-watch or a shell loop would.

Measured 2026-10-25, 4-vCPU Boat box (Linux 6.8 VM), median (min–max) seconds:

| variant | seconds | process state kept |
| --- | --- | --- |
| Minyar `--watch --hot` | 0.569 (0.427–0.728) | yes |
| Minyar `--watch` | 1.435 (1.412–1.516) | no |
| Rust `cargo build` + restart | 0.224 (0.191–0.343) | no |
| Go `go build` + restart | 0.268 (0.259–0.317) | no |

Only state retention favours Minyar here: its edit loop is 2–2.5x slower than
Rust's or Go's for this small service.
