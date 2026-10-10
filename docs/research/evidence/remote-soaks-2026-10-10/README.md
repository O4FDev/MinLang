# Completed remote baseline runs

Four independent 7,200-second runs finished on the dedicated DigitalOcean
Ubuntu 24.04 c-4 host on 10 October 2026. `manifest.json` identifies the
immutable source snapshot and executable hashes. Reports are verbatim;
compressed samples and stderr retain their uncompressed hashes. Generated
test keys and executables are excluded.

| Run | Scope | Exit | Warm RSS KiB | RSS slope KiB/s |
| --- | --- | --- | --- | --- |
| net-native | 4,096 TCP pairs, UDP, timers, reconnect/half-close | 0 | 2,944–2,944 | 0 |
| net-sanitize | Same workload, ASan/UBSan/LSan | 0 | 327,988–335,108 | 0.03485 |
| tls-native | 64 concurrent mutual TLS/HTTP clients | 0 | 7,296–8,004 | 0.10486 |
| tls-sanitize | Same workload, ASan/UBSan/LSan | 0 | 460,156–510,316 | 0.47300 |

The socket native process used 24.95 CPU seconds over 7,201.86 wall seconds
while exchanging 33,345,585 bytes and exercising recurring faults. Its
registry remained at 4,098 slots. Each TLS run established 5,021 connections
and handled 25,763 responses, including 432 malformed, 263 oversized and 331
slow responses, with no unexpected server or observer error.

These are concurrent-workload observations, not an isolated idle benchmark.
Native socket RSS was flat. TLS and sanitizer RSS increased; sanitizer
quarantine does not establish that all growth is a leak, and a successful
LSan exit does not establish perfectly flat memory. Raw samples are retained
for follow-up analysis. The baseline predates later crypto/QUIC changes and
does not validate those changes, QUIC migration, TCP fallback or peer-edge.

The separate QUIC baseline and later scale tests have their own evidence and
completion statuses. These four results must not be used to claim that the
entire requested system has passed a combined long-running test.
