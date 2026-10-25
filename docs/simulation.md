# Replaying a difficult night

Import `simulation` to run a single-owner model of disk, network delivery and
monotonic time. It performs no host I/O and starts no threads. Production code
needs an I/O boundary that can call this model instead of its real driver.
Importing the module does not intercept ordinary `files`, `net` or clock calls.

```minyar
use "simulation" as sim

let world = sim.create(42)
let file = sim.openFile(world, "/db/log", true)
sim.syncDirectory(world, "/db")
let write = sim.submitWrite(world, file, 0, Bytes("committed"), 10)
let written = sim.next(world)
let flush = sim.submitSync(world, file, 20)
let durable = sim.next(world)
sim.crash(world)
print(Text(sim.read(world, sim.openFile(world, "/db/log", false), 0, 9)))
```

The result is `committed`. Check completion `result` values before acknowledging
real work. A write submission copies its payload. It takes effect only when
`next` completes it; a sync covers writes completed before the sync. Submit a
sync after its required writes have completed. Two operations submitted together
may complete in either order, including a sync and a write to the same file.

`submitRead`, `submitWrite` and `submitSync` return unique operation IDs.
`submitPacket(world, channel, bytes, delayMs, token)` and
`submitTimer(world, delayMs, token)` add delivery and timer events. `next` returns
`Completion { id, token, kind, target, result, data, at }`. The earliest deadline
runs first; the seeded scheduler chooses among equal deadlines. A read returns
its byte count and a copied buffer; writes return their count; a sync or timer
returns zero. Errors are negative codes. `pendingCount` counts outstanding
operations; `cancel` removes one by ID. Calling `next` on an empty queue stops
with a clear message. IDs are not reused after cancellation or a crash.

Use `choose(world, count)` for application scheduling and generated workloads.
The generator is a bounded Park–Miller sequence with rejection sampling.
`choices(world)` returns independent `Decision { options, selected }` values.
Run the same scenario with `replay(seed, decisions)` to reproduce its choices.
Replay rejects a different choice count, an invalid selection or an exhausted
script. Check `finished(world)` afterward to reject an unused suffix too.
`fork(seed, decisions)` replays `decisions` exactly, then continues with fresh
choices from `seed`, as if created by `create(seed)`. Inside the prefix it
rejects mismatches exactly as replay does. The same seed and prefix give the
same run, and different seeds diverge only after the prefix. An explorer can
therefore branch many continuations from the moment a recorded run first
reached a rare state, instead of hoping a new seed reaches it again. The
transcript starts with `fork N`, the prefix length.
The seed alone reproduces a run only when the application and input are the same.
A decision script checks choice counts, not program identity: preserve the
source revision, fault scenario and input with a failing script. `transcript`
returns a copy of the operation log for retained evidence.

## Deterministic functions

A seed reproduces a run only if nothing else can change it. Mark the function
that runs one universe `deterministic`, and the compiler proves it:

```minyar
use "simulation" as sim

deterministic function universe(seed: Integer): Integer {
    let world = sim.create(seed)
    sim.advance(world, sim.choose(world, 10))
    return sim.now(world)
}

print(universe(7) == universe(7)) // true
```

The compiler follows every call the function can make, including calls into
other modules, generic instances, contract helpers, closures and the
initializers of the globals it reads. Nothing reachable may use a host clock,
randomness, files, sockets, process arguments, the environment, threads,
parallel execution, inline assembly, volatile machine access or native code.
Pure native libraries are allowed: `math`, `unicode`, `sha256`, `aes`,
`securecrypto` and `json` number parsing. A call through a callback value counts
as a call to every function whose address the program takes with that
signature, so a callback built by the caller is checked too. Any reachable Map
operation also reaches the key hash, equality and copy functions of every Map
the program creates, because a Map built by the caller carries them. The error names the
whole path:

```text
error: deterministic function 'simulate' can reach the host clock: simulate -> onCrash -> cover -> monotonicNanoseconds (native "system")
```

The marked function must be a named, top-level, non-generic Minyar function. It
may call generic functions and methods. Its callers keep ordinary host effects,
so a driver can read arguments, time a run or write reports around the
proved part. The check reads the final LLVM module, adds no instructions or
runtime calls, and runs only when a program uses the modifier. Programs that
use it compile with the complete frontend instead of reusing incremental
module state.

The proof covers effects, not every input. It does not track the contents
of a List, record or Map global that code outside the function changes, and it does
not make out-of-memory or stack exhaustion reproducible. Floating-point
`math` results are fixed for one build on one platform. `deterministic` is an
ordinary identifier everywhere except directly before `function`.

## Running many universes

In a project, put each scenario in `sim/NAME.min`:

```minyar
use "simulation" as sim

public function universe(seed: Integer): Text {
    let world = sim.create(seed)
    sim.advance(world, sim.choose(world, 10))
    if sim.now(world) > 9 { return "the tide came in late at seed \(seed)" }
    return ""
}
```

`minyar sim` builds each scenario in the release profile and runs seeds
`0..9999` (`--first`, `--seeds`); `--jobs` shares them between processes. The
generated driver calls `universe` through a `deterministic function`, so the
command refuses any scenario that can reach the host, and every reported seed
reproduces. A failure prints the lowest failing seed with its message, replays
it twice, and exits with status 1; `minyar sim NAME --seed SEED` runs that seed
alone.

## A disk with explicit durability

`openFile(world, path, create)` returns a positive file identity, or negative
`ENOENT` (`-2`). The synchronous `read`, `write`, `resize`, `size`, `syncFile`,
`rename`, `remove`, `names` and `syncDirectory` calls let existing I/O facades
use the same model. Reads return empty Bytes on error; inspect `lastError`
immediately. Names are exact lexical paths; directories and aliases such as
`..` are not resolved. File identities belong to their world and remain attached
to the same file through rename or unlink. Restart application handles after a
crash. This module is a simulation boundary, not an operating system handle API.

File contents and directory names have separate durable copies. `syncFile`
preserves contents; `syncDirectory` preserves only that directory's direct-child
names. Durable publication is write → sync file → rename → sync directory.
`crash` restores durable copies, discards pending completions and clears armed
one-shot I/O faults. A queued operation never runs after that crash. Network
partitions and virtual clock state remain under scenario control.

By default unsynced writes are lost. To model a torn write, call
`persistPrefix(world, file, count)` before crashing: exactly that volatile prefix
overlays the durable contents, extending their length when needed. The existing
durable suffix remains. Sweep every prefix of a new WAL record, and include
zero and full length. This is a deliberately bounded model of persistence; it
does not enumerate arbitrary sector reorderings, filesystem journals or hardware
that lies about completed syncs.

`injectError(world, kind, negativeCode)` fails the next matching `READ`, `WRITE`,
`SYNC` or `PACKET` operation without its ordinary side effect. Different kinds
leave it armed; faults of one kind are consumed in order. `partition(world,
channel, true)` drops that channel's deliveries with `-110` until healed.
`jumpClock(world, deltaMs)` changes wall time while timers continue to use
monotonic `now`. `advance` accepts only a nonnegative monotonic delta. Checked
Integer arithmetic also bounds the virtual clock.

The model copies buffers and durable images and searches lists linearly. Files
are bounded to 16 MiB each; they are not sparse. The queue, history and transcript
consume memory proportional to the scenario. Keep worlds bounded and create
fresh worlds for independent seeds. These are explicit testing costs, with no
runtime cost in applications that do not call the simulator.

## The database proof

`make check-simulation` checks replay, ordering, faults, durability and the
[harbour gallery](../examples/gallery/the-harbour-remembers.min) at O0/O2 with
ownership cleanup assertions. `make check-simulation-neodb` runs neo-db's actual
WAL, CRC and storage utility modules unchanged against a simulated `dbio` facade.
The pinned sources and provenance live under `tests/fixtures/neodb-simulation`.
The separate [manifest proof](simulation-manifests.md) checks real checkpoint
encoding, publication and recovery. These proofs do not qualify SQL transactions
or VM devices. The simulator is cooperative and explicit;
it neither explores arbitrary native thread interleavings nor replaces a real
kernel completion backend such as io_uring.
