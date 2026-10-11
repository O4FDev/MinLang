# TCP Result fixture sequencing

Reviewed source: `0b5e801ff06bf299871fac7866391ce902ebb5d8`.
The isolated Boat worktree is `/home/user/minyar-mac-net-review` on
`overnight/mac-net-review`. No local builds, edits, or macOS tests were run.

## Failure and diagnosis

Hosted macOS run `38108224749`, job `114378156051`, failed
`test_review_tcp_short_reads_and_eof_are_distinct` at O0. Its successful
three-byte sender write followed a false handle check and three socket read
errors. The fixture accepted immediately from a nonblocking listener.

The [Apple accept manual](https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man2/accept.2.html)
documents would-block when that listener has no queued connection, and read
readiness as the way to wait for a connection. An earlier readiness wait is
not a universal precondition for accept: an already queued connection can
be accepted immediately.

A real Linux kernel probe enables
[TCP_DEFER_ACCEPT](https://man7.org/linux/man-pages/man7/tcp.7.html), which
delays listener readiness until data arrives. With the maintained Minyar
provider, client connect succeeds while immediate accept returns
`-1/EAGAIN` and listener readiness is false. Sending `abc` then makes the
listener ready; accept and the exact two-byte, one-byte, EOF reads succeed.
The standalone probe passes O0/O2 both normally and under ASan/UBSan.

The new deferred-accept Result test runs the original Minyar program against
that real kernel option. Before the correction, both optimizations in native
and sanitizer profiles produce exactly the hosted failure output:

```
false
3
false
socket read failed
socket read failed
socket read failed
```

This reproduces the timing assumption without replacing connect, accept,
read, or their results with stubs. It does not establish the exact macOS
errno or claim that macOS uses Linux's deferred-accept option.

## Correction

The fixture sends its data after client connect, retains the typed write
Result, waits at most the existing 1000 milliseconds for listener readiness,
and then accepts. It prints and matches the retained Result in the original
order. Bounded readiness guards also precede the suffix and EOF reads.

The original exact stdout, successful write count, data bytes, non-EOF
short reads, final zero-byte EOF, O0/O2 execution, and frame/object/debt
assertions are unchanged. The provider, runtime, compiler, libraries,
global build wiring, catalogue, and launcher are unchanged.

The original normal fixture remains enabled on every platform. The new
test is explicitly a Linux TCP_DEFER_ACCEPT capability probe; it is
excluded elsewhere without implying a platform success.

## Evidence and verification

All source, generated wrapper, LLVM, executable, runtime, tool hashes, input
snapshots, subprocess observations and raw logs are retained under
`/home/user/minyar-overnight/mac-net-review`. Tests-first commit
`43b19be54404eef93d5af2685648def248591fd7` retains the actual failing
deferred-accept case.

Focused normal and deferred cases pass native and ASan/UBSan at O0/O2,
including Linux LeakSanitizer. Complete independent review and bounded
profile outcomes are recorded in `handoff.json`; no new compiler rebuild
was needed for this fixture change.

A fresh hosted macOS run of the normal fixture is still required. The
Linux reproduction and fix are not macOS verification.
