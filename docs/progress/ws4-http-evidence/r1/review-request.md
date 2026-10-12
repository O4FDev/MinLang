# HTTP independent review R1 — REQUEST_CHANGES

Reviewed `bf9c0e9..bd43f2b2f707f64bad569d452b291638cf8fdbe9` on clean `ws4/review-http-r1`. Scope: HTTP library, wire/API tests, build/catalogue wiring, cache-front fixtures, comparator and retained qualification evidence. No implementation, parent, index, downstream or baseline edits; no additional children, performance reruns, host lifecycle actions or paid spend.

## P2 — Backpressured half-closed clients busy-spin during response writes

**Location:** `library/httpserver.min:592` (phase-2 dispatch), `:397` (would-block return), `:429` (writable registration).

**Trigger:** A client sends a valid GET, calls `shutdown(SHUT_WR)`, and does not consume a response larger than the socket send buffer. Linux's existing event-loop backend always registers `EPOLLRDHUP` (`runtime/native/net_loop.h:353`). After the send buffer fills, it repeatedly emits closed-but-not-writable events. `advance` calls `flush` for all phase-2 events; `writeRange` returns -1 and leaves the permanently ready watch installed. Removing the watch during application wait does not cover this writing phase.

**Independent reproduction:** Exact candidate library, immutable compiler `f4f589…`, runtime IR `4119757…`, freshly linked owned native source, on `bx_ppv9fjr7:/home/user/ws4/review-http-r1`. External `hup-write-probe.min` serves 4 MiB with a 500 ms write deadline and observes the shared loop for 700 ms. The Python peer sets `SO_RCVBUF=4096`, sends `Connection: close`, and compares otherwise identical requests:

- Without half-close: 55 loop waits; 0 closed-but-not-writable events.
- With half-close: 495,440 loop waits; **495,411 closed-but-not-writable events** before the write deadline ends the stall.

Both fixtures exited 0 with empty stderr. Expected: blocked writes let the loop sleep while preserving deadlines and other clients' progress. Actual: continuous readiness/would-block work occupies the event-loop thread for the stalled write phase (default deadline 10 seconds). This is a concrete Linux CPU-exhaustion path, independent of the accepted transfer-coding restriction.

**Required:** Prevent persistent half-close readiness from spinning a blocked writer, preserving partial-I/O correctness and the fixed write deadline. Add a mandatory half-close + slow-reader regression that detects repeated immediate, nonwritable wakeups; the current separate half-close and slow-reader cases do not combine these conditions. Do not qualify Windows behavior from this Linux reproduction.

Repro sources, exact compile/link commands, results and receipts: [review-http-r1-evidence](review-http-r1-evidence/). Run the probe with the same direct compiler/owned-driver commands in `hup-write-probe-receipt.json`, then `python3 hup-write-probe.py` in the owned review namespace.

## Evidence and remaining qualification

The existing wire suite passed against my directly built release fixture (`cmd_5rgeukjbjvq5`, exit 0). Independent Python LRU/raw-byte and causal held-upstream HoL checks passed against my actual front (`cmd_demnkqz39uxx`, exit 0). Source hashes/modes and pinned baseline tools were verified before and after; all review subprocesses completed.

I independently checked all **16,434** archived samples: six complete round files; per round 548 miss/hit/stats/HoL-hit and 547 HoL-miss observations; contiguous indices, status/cache values, recorded body hashes and empty logs. Nearest-rank percentiles and median-of-three ratios reproduce every committed result exactly. The fixed 1.5x gate passes all five p50/p99 pairs; worst ratio is HoL-hit p99 **1.303613x**. Inputs match the original serving project's 548-query corpus and raw recording byte-for-byte, including original timing fields. Source blob hashes/modes at measured `283a5ad`, binary hashes and receipts agree. This is the stated deterministic compute-delay replay domain, not live-engine execution; no sample subset, normalization or threshold change was used.

The NUL-key, AppleDouble and missing-workflow reds remain retained and truthfully described. The shared correctness compiler `0b8bd2…` is distinguished from quiet timing compiler `f4f589…`. Build wiring includes wire tests in check/portable/sanitizer and actual-front controls in check/portable, with no new native package or Map dependency. macOS receipts establish the stated small O0 kqueue wire/front checks; they do not establish broader Mac qualification.

**Still unqualified:** actual Windows execution, shared programme <=1% performance gates, full platform integration, integrator merges and downstream fixed-in-v2 annotations. The valid retained HTTP benchmark result does not resolve the code finding above.
