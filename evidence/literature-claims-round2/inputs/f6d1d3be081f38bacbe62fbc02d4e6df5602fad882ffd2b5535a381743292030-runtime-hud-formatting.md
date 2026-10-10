# Application Integer formatting and intentional cache retention

This count-only baseline projects the Integer-to-Text calls in Craft's
`twoDigits`, `clockText`, and HUD construction at
`examples/craft/main.min:66–92`. It runs a real generated headless program with
already-floored coordinates and an integer minute counter. It does not replay
physics, Float sky-time conversion, graphics, a display, or frame latency.
The [approved pre-execution design](runtime-hud-formatting-proposal.json) pins
that application source and scope. No production code or cache policy changed.

Each frame formats FPS 60, x, y=64, z=-1, hour and minute: **six public
`minyar_integer_text` calls**. The clock advances from minute 360 modulo 1440.
Three trajectories set x to `16 + frame % 16`, `frame`, or `-(frame + 1)`.
Each process runs the same 2,048 frames twice, starting with an empty Integer
cache. Cold and warm describe these two passes. Exact status strings are compared
against an independent Python oracle, and the first status survives the second
pass through an explicit alias. Native shadow aliases also revalidate every
cached Text's content and identity at checkpoints.

| Trajectory | Public conversion calls per pass | Default allocating conversions, cold / warm | Disabled-control allocating conversions, cold / warm | Intentional default cache objects / requested bytes |
| --- | ---: | ---: | ---: | ---: |
| Bounded positive x=16..31 | 12,288 | 2,110 / 2,048 | 12,288 / 12,288 | 62 / 3,648 |
| Increasing positive x=0..2047 | 12,288 | 4,096 / 2,048 | 12,288 / 12,288 | 2,048 / 123,818 |
| Negative x=-1..-2048 | 12,288 | 4,158 / 4,096 | 12,288 / 12,288 | 62 / 3,648 |

“Allocating conversions” counts actual private `format_integer_text` entries,
each making one Text-header and one data allocation. Public conversion calls
remain equal across policies. The default cache stores only nonnegative values
below 32,768. Thus z=-1 allocates on every frame in all trajectories; the negative
trajectory's x also allocates every frame. Its warm residual 4,096 is not a cache
failure. FPS, y and the clock together visit 62 cached values; the positive x
trajectory extends that union to 2,048.

The default static pointer-table extent is **262,144 bytes**, separately from
cached objects' requested allocations. This is a declared static storage extent,
not committed/RSS memory or buddy charge. The test observer has its own separate
262,144-byte shadow-pointer registry, reported explicitly. Disabling the cache
uses the existing `MINYAR_INTEGER_TEXT_CACHE_LIMIT=0` build control and removes
the runtime table. It is a test-only cache policy control, not a proposed or
accepted optimization.

Inside Integer conversions, each allocating conversion invokes two K32 helper
services, offering 64 queued-work credits. Default cold/warm offers are
135,040/131,072 for bounded, 262,144/131,072 for positive, and 266,112/262,144 for
negative; the disabled control offers 786,432 each pass. **Actual conversion-scoped
queued work is zero in every observed case.** No equivalence under cleanup debt,
fragmentation or allocation pressure follows from these idle observations.
The counters exclude HUD join allocations and caller releases. Offered credits,
actual queued work and observer drain work remain distinct fields.

After releasing the two saved status aliases and draining queued work, exact
objects/requested bytes equal the independently predicted permanent cache only.
After test-only frame-cache disposal, heap allocation count equals two per cached
entry. The disabled control recovers to zero objects, requested bytes and heap
allocations. The default's lasting cache is intentional and bounded; it is not
reported as a leak or zero-memory recovery. Summed allocation-request bytes
during conversion are not peak or retained bytes.

The 16-frame pilot first validates instrumentation, output and expected counts.
It makes 96 public conversions each pass; the default performs 50/16 allocating
conversions versus 96/96 in the disabled control, retaining exactly 34 cached
objects/1,996 requested bytes. The main matrix then passes 18 generated executions:
three trajectories, two policies, and O0/O2 native links or O1 ASan links. This is
73,728 configuration-weighted frame executions, not distinct application scenarios.
All 15 generated definitions carry ASan in sanitizer runs; runtime C additionally
has ASan/UBSan. Generated UBSan and LSan are not claimed. No timing or speedup
claim is made while the paced sustained cohorts share the host.

Run:

```sh
python3 tests/memory-research-hud-formatting.py --pilot
python3 tests/memory-research-hud-formatting.py
```

Durable [pilot](evidence/runtime-hud-formatting/run-ar18ynek/results.json) and
[main matrix](evidence/runtime-hud-formatting/run-xm7s2ljs/results.json) retain
source/compiler hashes, exact instrumentation diffs, commands, counters and
verified complete output hashes. Large output and binaries remain disposable;
the archived independent generator reproduces the full expected output.
The counts motivate accounting awareness, not a new cache implementation.

A smaller prefix cache is not adopted. Craft coordinates and FPS do not promise a
small positive range, and the negative trajectory already exposes uncached work.
Reducing the current prefix would change repeated pointer identity for previously
cached values and replace immortal values with managed owners. That can change
reference-List scan debt as well as allocation and cleanup-service histories.
A sparse identity-preserving registry would add metadata allocations and new
failure behavior. These objections do not prove every smaller policy impossible;
the measured counts do not justify such a production change. The limit-zero
configuration remains only a cache-policy control.
