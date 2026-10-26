# Live patch under load

`server/` is a small stateful HTTP service: `reply()` counts requests in a module
global. `run.py` keeps eight keep-alive clients busy (`load.go`) and changes
`reply()` from `version=1` to `version=2` while it serves:

- `hot`: `minyar run --watch --hot --release`; the edit is a source save.
- `restart`: two plain `--release` binaries; the edit stops v1 and starts v2 on
  the same port, as a process-per-version deploy does.
- `patch`: `minyar build --hot --release`, run the binary without a watcher,
  then publish the edit with `minyar patch`.
- `steady` / `watch`: no edit; hot mode, the plain release binary and ordinary
  watch mode, for dispatch cost. `LIVEPATCH_PERF=1` adds the server's user-mode
  instructions per request (`perf stat`).
- `soak`: like `patch`, but publishes one edit after another for the whole run,
  then checks every request (no error, versions monotonic per connection, each
  request counted once) and reports the server's resident memory.

```sh
python3 benchmarks/livepatch/run.py hot restart steady watch
```

Each run prints JSON: errors, versions seen, the request counter's value on each
side of the change (`last_v1_served`, `first_v2_served`), time from save to the
first v2 response, and the longest pause between responses.

`make check-live-patch-load` is the regression form: four Python clients, a debug
hot session, zero failed requests, monotonic versions per connection, and every
request counted exactly once across the update.

Measured 2026-10-25 on a Boat box (8 vCPU Linux 6.8 VM, LLVM 23.1.3, server on
CPUs 0-3, load on 4-7; three rounds each):

| | failed requests | counter after change | save → first v2 |
| --- | ---: | --- | ---: |
| hot | 0, 0, 0 | continues (e.g. 299118 → 299119) | 0.60–1.17 s (compile) |
| restart | 24, 16, 16 | resets to 1 | 2.7–4.6 ms (prebuilt) |
| `minyar patch`¹ | 0, 0, 0 | continues (e.g. 377176 → 377177) | 0.69–0.98 s (the patch command) |

¹ Measured on a 4-vCPU Boat box, server on CPUs 0-1 and load on 2-3; the
instruction counts below come from both boxes and agree for the shared modes.

Hot-mode dispatch, server user instructions per request (three rounds each):
plain release 38.7–38.9k, watch without `--hot` 38.6–38.8k; hot 58.3–58.4k with
the original locked resolver, 49.4–49.6k with a lock-free cached one, and
42.0–42.1k with per-function slots and the published epoch (+8.5%). A
`build --hot` binary patched mid-run: 42.2–42.4k.

Twenty successive `minyar patch --release` runs on the idle server (4-vCPU
box): with whole-program update images each took 0.66–1.11 s and resident
memory grew 2,800 → 8,088 KiB (~265 KiB per patch); with images holding only
changed functions, 0.29–0.37 s and 2,780 → 4,336 KiB (~78 KiB per patch).

Soak, 2026-10-26, 8-vCPU box as above, 45 s of load (two rounds):
`minyar patch --release` back to back published 148 patches per round
(0.27–0.41 s each) while the clients completed 6.82M requests with 0 errors,
monotonic versions on every connection and every request counted once; the
server ended at 18.5–18.7 MiB resident, since every published image stays
loaded.
