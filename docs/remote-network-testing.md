# Remote networking tests

Sustained tests and performance measurements run on remote Linux hosts. The
long-run drivers require `MINYAR_REMOTE_LAB=1` and reject macOS execution, so
their default two-hour run cannot accidentally load the development laptop.

The initial DigitalOcean lab uses Ubuntu 24.04 on a CPU-Optimized `c-4`
(4 dedicated vCPUs, 8 GiB RAM, 50 GiB disk) and a separate `c-2` peer
(2 dedicated vCPUs, 4 GiB RAM, 25 GiB disk). API prices at creation were
$0.125/hour and $0.0625/hour. A 24-hour lifetime costs at most $4.50 in compute;
no backups, snapshots, volumes or load balancers were enabled. Each host has
an independent root-owned deletion guard with an absolute deadline and a
5 GiB transmitted-byte ceiling. The guard checks the exact droplet ID, name
and task tag before deletion. Tests run as an unprivileged account. The $10
incremental infrastructure cap covers both hosts and transfer; unrelated
existing account resources are outside this lab's ledger.

The guard and its credential stay outside the repository. SSH is restricted
to the operator address; inbound test traffic is restricted to lab peers.
Destroy both droplets after collecting evidence, verify their absence through
the provider API, and then remove the task firewall and SSH public key. Power
off alone does not end DigitalOcean billing.

Use isolated source/build directories and record the source and executable
hashes, compiler versions, CPU model, host load and elapsed time. Run paired
performance comparisons under a host-wide measurement lock without a build
or traffic generator competing for CPU. Record PMU availability; wall-clock
and CPU time cannot substitute for an unavailable instruction counter.

```sh
export MINYAR_REMOTE_LAB=1
export MINYAR_LLVM_BIN=/usr/lib/llvm-23/bin
export MINYAR_TEST_CLANG=clang-23
python3 tests/net-soak.py --seconds 7200 --connections 4096 --output build/net-soak
python3 tests/tls-soak.py --seconds 7200 --connections 64 --output build/tls-soak
```

Run native and `--sanitize` variants in separate artifact directories. Linux
sanitizers enable leak detection and stop on undefined behaviour. The socket
test keeps thousands of TCP sockets open while delivering UDP batches,
truncation, omitted/reversed datagrams, repeating timers and peer half-closes.
The TLS test uses Minyar TLS 1.3/mutual TLS and HTTP keep-alive against an
independent OpenSSL server with delayed, malformed and oversized responses
and repeatedly closed peers. QUIC has its own independent peer/fault harness;
neither foundation driver claims QUIC coverage or TCP fallback coverage.

`soak_observer.py` samples process RSS and CPU from `/proc` independently of
client output. It bounds log lines, handles fragmented output and kills the
whole child process group if the absolute test deadline is exceeded, including
when a parent exited but a descendant retains stdout. Reports contain warmed
RSS minimum/maximum and a least-squares RSS slope, plus raw samples. Assess
memory and CPU after warm-up and during a separate quiet idle window; a zero
exit code alone does not establish flat memory or low idle CPU. Retain failed
and interrupted evidence with its completion status. Interrupted laptop runs
are incomplete and cannot establish long-run results.
