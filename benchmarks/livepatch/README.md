# Live patch under load

`server/` is a small stateful HTTP service: `reply()` counts requests in a module
global. `run.py` keeps eight keep-alive clients busy (`load.go`) and changes
`reply()` from `version=1` to `version=2` while it serves:

- `hot`: `minyar run --watch --hot --release`; the edit is a source save.
- `restart`: two plain `--release` binaries; the edit stops v1 and starts v2 on
  the same port, as a process-per-version deploy does.
- `steady` / `watch`: no edit; hot mode, the plain release binary and ordinary
  watch mode, for dispatch cost. `LIVEPATCH_PERF=1` adds the server's user-mode
  instructions per request (`perf stat`).

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

Hot-mode dispatch, server user instructions per request (three rounds each):
plain release 38.7–38.9k, watch without `--hot` 38.6–38.8k, hot 58.3–58.4k
before the lock-free cached resolver in `tools/live-runtime.c`, 49.4–49.6k after.
