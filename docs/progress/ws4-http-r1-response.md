# HTTP R1 response

Review: REQUEST_CHANGES, one P2 write-phase half-close/backpressure busy spin.
Reviewed base bd43f2b; fix 1751f1e2367461563ad9ec382b6827218127a027.

The independent repro is valid. Writable-only and zero-interest watches still
receive persistent HUP notifications. The fix removes a write watch as soon as
HUP is observed, keeps the socket and complete unsent body, and uses direct
bounded write probes. Would-block schedules the next probe in 10 ms; successful
I/O-budget consumption permits the next bounded advance turn. Shared-loop
waitMilliseconds clamps to both probe time and the original write deadline.
No callback, timer registration, native package, kernel, ownership or shared
driver change is involved. FIN alone never discards a valid response.

Mandatory tests/httpserver-write-wait.min is invoked by tests/httpserver.py in
all normal debug/release/sanitizer Make gates. It combines valid request/FIN,
SO_RCVBUF4096 and an unread 4 MiB body at a fixed 500 ms write deadline. A 700 ms
observer requires <=300 waits and <=4 closed-only events. It also checks an
unrelated small reply, an external repeating shared-loop timer, exact 4 MiB
delivery after reading resumes, zero live connections and deterministic loop
cleanup. Existing protocol, pipeline, body, deadline, LRU and HoL tests remain.
Direct binary checks require both --binary and --write-binary; focused
--write-only is only used for test-first reproduction, not full qualification.

Retained test-first red on the original API: 530995 waits / 530965 closed-only,
exit1. An intermediate removal-only-after-would-block fix still produced nine
closed-only events and failed the unchanged <=4 bound. The final fix removes
the watch immediately on HUP; no test limit was raised.

Exact-source baseline f4f589 compiler and 4119757 runtime IR qualification in
owned bx_ppv9fjr7:/home/user/ws4/http-r2 passed debug/release and generated
LLVM/native/runtime ASan+UBSan+LSan, all prior wire tests and front controls.
Stalled FIN waits debug104/release107/sanitizer101, one closed-only event each;
resumed FIN108/107/107 with exact complete bodies. Each had35 timer ticks and
zero active connections. Job PID71856/cmd_cbur7ot2tkam exited0. Source/mode and
immutable tool checks ran before and after. The exact qualification runner,
command/exit rows, source inputs and object/header hashes are retained.

Small unprivileged Mac O0 wire/observer checks also passed: stalled FIN46/1,
resumed FIN102/1, exact body,34 timer ticks and zero active. Cached compiler and
previously compiled candidate runtime/net source/object SHA were rechecked.
No bootstrap, local privilege or security mutation occurred.

Original 283a5ad/bd43f2b benchmark evidence is preserved. Corrected source was
rebuilt on the exclusively admitted bx_8b8ercp7:/home/user/ws4/http-bench using
the immutable compiler/runtime and verified source/mode manifest. The first
corrected full default gate (source1751f1e, acceptance-r1-fixed) failed hit
p99:1.6303x (188.1/115.4us); other nine cells passed. The entire failed run is
retained, with source/binary/command/sample identities.

Performance change f6d9dfb792908410c374f6bfaeb4fa9dd6414a1c packs bodies up to
64 KiB with headers into one bounded output buffer, removing separate
TCP_NODELAY writes and receiver wakeups. Larger bodies remain borrowed/no-copy;
the I/O budget, write deadline and HUP probe strategy are unchanged. The fixed
gate itself, corpus, delays, round count and all cohorts were not modified.

The full default acceptance-r1-coalesced run passed every p50 AND p99 cell on
the same exclusive host, PID33933/cmd_qimunor8awk8, exit0 at15:46:48UTC.
Ratios p50/p99: miss0.970/0.989; hit0.943/0.811; stats1.048/1.103;
HoL miss0.971/0.992; HoL hit0.986/0.647. Worst1.103x. Raw identity/LRU/causal
HoL/concurrent overlap all passed. Pre/post immutable f4 compiler/411 runtime,
source/mode/tool and binaries9669331e/ca024dd7 were verified. Complete failed
and passing samples/receipts remain in ws4-http-evidence/r1; no retry selection.

Test-only64bb2e9082381ffe2c225eacc34f4ca8a5c34309 adds an ordered binary POST
pipeline with empty,65535,65536,65537-byte replies, exact Content-Length and
byte equality. Existing HEAD/204/205/304 and resumed4MiB FIN remain. Final
source-bound debug/release/ASan+UBSan+LSan plus all prior protocol/front controls
passed again in own namespace (PID79356, exit0), and bounded Mac checks passed.
Final stalled FIN waits115/101/116, closed-only1/0/1; resumed108/108/107 with
complete body and35 timer ticks/zero active each. Final Mac stall49/1 and
resumed102/0, complete body and34 ticks/zero active. These test-only additions
do not change the product code measured atf6d9dfb.

Actual Windows execution, independent R2 review, programme-wide performance
regressions and root integration remain separate pending gates. This response
does not claim them complete. Parent supplies R2 review with original brief,
R1 finding/evidence, this reply and corrected source/evidence SHAs.
