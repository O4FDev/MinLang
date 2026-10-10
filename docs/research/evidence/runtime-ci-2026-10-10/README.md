# Runtime native CI evidence, 2026-10-10

The isolated runtime branch is draft PR [7](https://github.com/O4FDev/MinLang/pull/7)
against `feat/v2-desktop-services`. Ordinary engine and ownership headers are
unchanged. Historical remote independent graph, closure, ownership and coverage
evidence remains in `../managed-graphs-2026-10-10/`.

## Actual Windows workers: red then green

The red test commit `7ab8ece` enabled all eight copied-process worker tests on
Windows, including every truncated/oversized message prefix, empty versus EOF,
malformed output, snapshots/stale IDs, bounded backpressure, and modes containing
empty strings, Unicode, quotes, spaces and trailing backslashes. The actual
[Windows 2025 job](https://github.com/O4FDev/MinLang/actions/runs/38065093995/job/114251072418)
failed with 23 assertions against the previous unavailable backend.

The implementation committed in `5c6c4de` adds stable overlapped state and
buffers, bounded copied queues, restricted inherited handles, correctly quoted
UTF-16 arguments, and process job cleanup. All eight unskipped tests passed in
15.872 seconds on native Windows 2025 at commit `3f7f658` in the
[green job](https://github.com/O4FDev/MinLang/actions/runs/38065662029/job/114252660498).
Remote MinGW warning-clean cross-compilation is additional portability evidence;
it is not substituted for that native execution.

## Actual macOS ordinary resource checks

The [macOS arm64 job](https://github.com/O4FDev/MinLang/actions/runs/38065093995/job/114251072392)
at commit `7ab8ece` built the ordinary compiler, checked its stage 2/3 fixed
point, and ran the original unmodified absolute budget test. On Apple M1
(Virtual), Darwin 24.6.0, Apple Clang 17, it reported:

| Metric | Measured | Unchanged ceiling |
| --- | ---: | ---: |
| Best-batch wall p90 | 11.29 ms | 25.00 ms |
| Best-batch CPU p90 | 9.82 ms | 22.00 ms |
| Peak RSS | 9.5 MiB | 10.0 MiB |
| Retired instructions | Unavailable | 75 million |

The original budget test printed `self-compile budget met`; its existing policy
checks retired instructions only if `/usr/bin/time -l` supplies that metric.
The ordinary `check-performance` suite also passed. An added workflow
completeness guard failed because the VM supplied no instruction counter. That
failure does not establish a performance regression, and the missing metric
does not establish that the instruction ceiling passes. No threshold changed.

A separate [probe workflow](https://github.com/O4FDev/MinLang/actions/runs/38065662083)
checks the supported public-repository M1 and Intel Mac runners with `time -l`
and a bounded Instruments CPU Counters recording. Both Mac runners omit retired
instructions and cycle counts from `time -l`; both Instruments recordings timed
out after the explicit 30-second probe limit. An absent counter remains an
unmeasured ceiling. The original budget script and all four numeric limits stay
unchanged. The added mandatory availability guard was removed from the required
job after confirming that both standard Mac runners lack it; the required job
now makes the absence prominent in its summary and archived evidence. No paid
Mac was provisioned, and no laptop test or performance program was run for this
integration.
