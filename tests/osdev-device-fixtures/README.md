# Actual-driver host device fixture

`driver.min` imports the production e1000 driver, production `device.Memory`
and production PCI scanner. Only the package modules `machine` and `arch` are
injected, with this library path first:

```text
build/minyarc tests/osdev-device-fixtures/driver.min /tmp/e1000-model.ll \
  --library tests/osdev-device-fixtures/library --library library
```

Use `tests/osdev-devices.min` through the normal test runner on BX. It selects
the compiler/runtime/Clang from `MINYAR_TEST_*`, compiles the fixture once, links
at O0/O2, and caps each child command at 60 seconds. Its default mode retains
all RX rejection oracles and fails if any remain red. `--positive-only` is an
explicit narrower bring-up mode which announces that those oracles were skipped.
No run is authorized on the laptop by this fixture.

The linked fixture accepts one scenario argument:

| Scenarios | Expected behavior |
| --- | --- |
| basic | Real scan/start, exact TX/RX copies and exact protocol transcript |
| tx-reorder | 32 outstanding staged transmissions, backpressure, delayed/reordered DD, stale/duplicate/range controls |
| tx-wrap | 96 actual sends, descriptor reuse only after DD observation and acquire |
| rx-reorder | Out-of-order DD exposure, FIFO consumption, IRQ-only wake and stale/duplicate/range controls |
| rx-wrap | 133 actual receives across the exclusive RX tail and generation changes |
| copy | Actual typed Memory overlapping copy, fill and sentinels |
| unknown-address, port | Hard model failure without foreign dereference or port execution |
| unpublished, unacquired | Hard model failure for missing publication/acquire fences |
| bad-descriptor | A bad DMA address hard-fails inside owned-address lookup |
| rx-oversized, rx-fragment, rx-error | Reject the frame without increasing received |
| tx-oversized | An empty or larger-than-buffer frame is refused, never truncated |
| rx-fragment-tail | An oversized frame is dropped through its end-of-packet tail (Linux CVE-2009-4536) |
| seeded FIRST COUNT STEPS | Seeded fault campaign (below) |

The model retains every registered Bytes owner and checks its address/size remain
stable. The sole native call is the actual raw machine `address(Bytes)` intrinsic.
CPU reads/writes use safe Bytes indexing; device snapshots are separate. A CPU
fence publishes pending CPU bytes. Device completions expose DD first; metadata
and payload remain hidden until the driver observes DD and then fences. Tail
writes verify ownership and publication. Every unregistered address or unknown
MMIO/port operation stops the fixture. Slot generations validate device-script
legality; legacy hardware descriptors do not carry a generation tag, so this is
not a claim that the driver can identify arbitrary stale physical DMA writes.

The model samples each TX doorbell immediately and stages that DMA packet while
allowing DD completion to be delayed/reordered. It models descriptor protocol,
not Ethernet filtering/padding/FCS or arbitrary NIC timing. RX reserves one tail
slot, consistent with QEMU's head != tail availability.

## Seeded fault campaign

`driver seeded FIRST COUNT STEPS` runs COUNT seeds. For each seed a
`simulation.World` (library/simulation.min) makes every device decision: when to
send, when each TX completion fires (delayed and reordered through World
timers), duplicate completions, missed and spurious interrupts, and RX frames
that are well formed, errored, or oversized two-descriptor chains. After a drain
it checks that every well-formed frame arrived exactly once and in order, no
malformed frame or fragment tail was ever delivered, and the TX bytes match.
Each seed prints a trace digest over the World transcript and the model's event
log, so `tests/osdev-devices.min` requires identical output at -O0 and -O2: the
same seed replays the same interleaving. A failure names its seed; rerun with
`seeded SEED 1 STEPS` to reproduce it.

Before the driver fix the campaign failed on seed 1 (a malformed frame was
delivered). With only an end-of-packet and error check it still failed on seed
1: the tail of an oversized frame was delivered as a frame, the CVE-2009-4536
bug class. The driver now drops a multi-descriptor frame up to and including its
tail.
