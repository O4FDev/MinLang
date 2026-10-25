# Server memory per idle keep-alive connection

`run.py` starts each server, warms it with 100 requests on one connection, then
opens N connections, completes one request on each and keeps them open. It
reports the server's VmRSS growth divided by N.

- Minyar: `benchmarks/livepatch/server` (library/httpserver.min), `--release`.
- Go: `server.go`, net/http, one goroutine per connection.
- Rust: `rust/`, current-thread tokio 1.54.1 (`Cargo.lock`), one task per
  connection with a 4 KiB read buffer.

```sh
python3 benchmarks/connections/run.py 1000 3
```

Measured 2026-10-25, Boat box (Linux 6.8 VM), 1000 connections, every round
identical to the byte:

| server | bytes per idle connection |
| --- | ---: |
| Minyar before the adaptive read size | 66,810 |
| Minyar after | 5,435 |
| Go 1.23.4 net/http | 15,704–15,905 |
| Rust tokio 1.54.1 | 4,989 |

Before the change every read reserved the full 64 KiB I/O budget in the
connection's input buffer, and keep-alive connections kept that capacity. Now a
connection with nothing buffered reads 4 KiB; a request that needs more gets
full-budget reads. POST throughput, 4 Go clients, three paired rounds (old /
new requests per second): 1 KiB 91.6k/112.3k, 104.6k/82.9k, 132.1k/111.2k;
64 KiB 48.1k/58.9k, 49.3k/55.7k, 65.5k/63.6k; 1 MB 10.4k/10.0k, 11.0k/10.0k,
9.6k/9.2k (4-vCPU box; noisy, the 1 MB case is 4–9% slower). A first attempt
that also released storage after large requests cost 20–40% on 64 KiB and
1 MB bodies and was dropped.
