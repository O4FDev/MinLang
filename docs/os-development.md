# Developing a kernel

`tools/osdev.py` builds with the existing `os/Makefile` and starts QEMU with the
same hardware devices. It runs on Linux and macOS with Python 3.9 or later,
LLVM (`clang`, `ld.lld`, `llvm-objcopy`), Make and QEMU installed. Every build first
checks `build/minyarc` through the public `tools/toolchain.sh bootstrap` path, then
builds the OS through `os/Makefile`. This uses the same incremental graph, locking,
compiler flags and interactive resource policy as the nested `./minyar` launcher.
Compiler changes cannot leave a stale existing compiler in use, and equivalent
flag quoting does not alternate the compiler's toolchain stamp between paths.
The commands below run from the repository
root; `--root /path/to/Minyar-OS` selects the neighbouring OS checkout instead.
Relative `--kernel-source`, `--log` and `--elf` paths resolve from the current
working directory. `--root` changes the checkout used for builds and default
artifacts, so use an absolute kernel-source path when selecting another checkout.

```sh
python3 tools/osdev.py run
python3 tools/osdev.py run --arch arm64
python3 tools/osdev.py debug --arch x86_64
```

Output goes to the terminal and a fresh `build/os/ARCH/osdev-serial.log`.
`--log PATH` chooses another log. Each run replaces that log, so preserve failing
logs before rerunning. QEMU uses a temporary disk overlay (`snapshot=on`), and
guest disk writes are discarded on exit. A missing tool, failed build or missing
artifact stops the command before QEMU starts.

The default display is headless (`none`); use `--display cocoa` on macOS or
`--display gtk` with a QEMU build that supports GTK. A headless desktop still
boots and reports serial output. TCG emulation is selected explicitly for both
architectures, including cross-architecture runs. Arm selects
`virt,gic-version=3`, matching the kernel entry code's GICv3 CPU interface.
The existing `make -C os run`
remains available for the platform's original display and accelerator choices.
`os/tools/qemu-drive.min` remains the scenario runner for keyboard, pointer and
screenshot checks.

Inspect every command before running it:

```sh
python3 tools/osdev.py run --dry-run
python3 tools/osdev.py debug --arch arm64 --gdb-port 9123 --dry-run
```

Dry runs execute no tools and create no logs. The output shell-quotes each
argument for review; commands themselves run as argument arrays. `--qemu PATH`
and `--make PATH` each select one executable. `--llvm-bin DIRECTORY` (or the
`LLVM_BIN` environment variable) selects the build tools; otherwise the wrapper
uses the directory of `clang` on `PATH`. Both build phases and their nested
launchers receive that selected compiler through `MINYAR_CLANG` and `LLVM_CC`;
explicit `COMPILER_LTO_FLAGS` values are preserved. A temporary PATH entry named
`make` points to the selected `--make` executable for public bootstrap and nested
launchers, then is removed. Dry runs describe this selection without creating it.
The existing Makefile's recipe paths
are not fully quoted, so actual builds require a checkout path without spaces.
Already-built images can be run from paths with spaces or commas.

`--rtc-base 2026-10-20T12:34:56` selects a fixed initial QEMU calendar with
`clock=vm`. The calendar advances as the guest runs; initial seconds are not
frozen. Invalid dates and extra QEMU options reject before any tools run.

The OS build selects the ordinary or managed graph runtime separately for the
loader and kernel from each program's compiler-emitted LLVM markers. Callbacks
use the same graph engine as hosted programs. The bare callback profile binds
its execution domain to the boot CPU during argument initialization, before
module constants and the kernel body run. Physical CPU checks reject callback
use from another CPU; hosted callbacks retain their thread-local identities.
The bare allocator, RC and frames remain a single execution domain: managed AP
work, migration and callback entry from interrupts or NMIs are unsupported.
Callback creation allocates before its domain is recorded, so the CPU check
does not authorize managed allocation on other CPUs. Managed thread runtime
requests reject explicitly in this OS profile. Existing compiler-checked
scalar data parallelism retains its bare serial fallback and optional kernel
scheduler; it does not invoke managed callbacks on worker CPUs.

`check-osdev-runtime` checks engine selection and rejected configurations.
`check-osdev-callback-domain` checks domain identity boundaries and foreign-CPU
rejection, and cross-compiles the real provider for x86-64 and Arm without TLS.
Both checks are included in `check-osdev-freestanding`.

## Finite kernel tests

Use a kernel that prints a unique success line, then exits with status zero:

```sh
python3 tools/osdev.py test --arch arm64 \
  --kernel-source os/tests/fields-kernel.min \
  --expect 'OSDEV FIELDS PASS' --timeout 30
```

`make check-osdev-qemu` runs this Arm test; `OSDEV_ARCH=x86_64` selects the
PC boot path. Both guests exercise PCI discovery, the real e1000 driver's
packed descriptors and checked TCTL fields, then exit. The legacy QEMU e1000
does not emulate TIPG; its exact register bytes are checked by the host suite.
The freestanding square-root shim uses a direct floating-point intrinsic:
the libc-style builtin could otherwise lower to a recursive call to `sqrt`
and an undefined result. The guest checks a device-written descriptor length's
square root; the portable gate also verifies native SQRTSD/FSQRT instructions.

The runtime's typed whole-file I/O is unavailable in freestanding programs:
valid requests return native error38 (ENOSYS), and negative limits or zero-byte
paths return22 (EINVAL). Kernel disk drivers remain independent of those hosted
APIs. `check-osdev-freestanding` excludes host headers while cross-compiling both
runtime units for both architectures.

The wrapper passes `KERNEL_SOURCE` to the Makefile and forces the selected kernel
to rebuild on every invocation, even when the test source is older than the
previous desktop kernel. Compiler, runtime and other prerequisites still build
incrementally. It writes the usual architecture's build artifacts. A subsequent
`osdev.py run` rebuilds the default desktop kernel; this prevents an earlier test
kernel from silently standing in for it. Direct Make invocations do not remember
the override: use the wrapper to restore the default kernel before returning to
the original `make -C os run` workflow.

Tests pass only when the guest prints the exact requested line and QEMU exits
with the architecture's successful status. A substring or an old log cannot
satisfy the check. Host diagnostic output is separate from the guest's serial
output. A serial panic, processor exception, `Minyar stopped:`, runtime error or
nonzero Minyar exit report fails the test even after the success line.

On x86-64, the freestanding runtime writes its exit status to QEMU's
`isa-debug-exit` device. Guest status zero gives QEMU process status **1**; this
one status is accepted by x86 tests. On arm64, the runtime issues PSCI
`SYSTEM_OFF` and QEMU exits with process status **0**. Both paths additionally
need the requested serial line. These are contracts of the current freestanding
runtime; an unrelated QEMU process exiting successfully is insufficient evidence.

The test deadline defaults to 30 seconds and starts after the build. Timeout
returns **124**, including a guest that prints success and then hangs. Closing
serial output without exiting does not bypass the deadline. The desktop kernel
normally runs forever and is therefore unsuitable for this finite test contract.
The compiler check and OS build share one 600-second deadline (`--build-timeout`). The wrapper
terminates and reaps the process group when a deadline or interruption occurs.
Interactive `run` and `debug` have no QEMU deadline unless `--timeout` is supplied.

`--no-build` runs existing artifacts; it is useful when preserving the exact
kernel that caused a fault. It cannot be combined with `--kernel-source`.
Run the focused wrapper regression suite with:

```sh
python3 tests/osdev-workflow.py
```

That suite uses fake build, QEMU and symbolizer executables. It proves orchestration
and failure detection without booting a guest; a real kernel boot is a separate
integration check. Under the moonshot charter, run both kinds of check through
`bx`, never on the shared laptop.

## Debugging and symbolizing faults

`debug` starts QEMU stopped (`-S`) with its GDB server bound to loopback. The
command prints the matching ELF and debugger connection command:

```sh
python3 tools/osdev.py debug --gdb-port 1234
gdb build/os/x86_64/kernel.elf -ex 'target remote 127.0.0.1:1234'
```

Use a GDB build supporting the target architecture; `continue` begins execution.
When QEMU runs on a remote build box, forward the loopback GDB port through SSH
and preserve the matching ELF locally.

The x86 exception stub already prints `rip`; the Arm exception handler prints
the faulting instruction after `at`. Symbolize those instruction addresses with:

```sh
python3 tools/osdev.py symbolize --log build/os/x86_64/osdev-serial.log
python3 tools/osdev.py symbolize --arch arm64 0x40080040
python3 tools/osdev.py symbolize --elf saved/kernel.elf --log saved/serial.log
```

The command selects `llvm-symbolizer`, falling back to `addr2line`; choose a
specific executable with `--symbolizer PATH`. A log extracts RIP, ELR, PC and the
Arm handler's instruction address, excluding stack pointers, fault addresses and
syndrome registers. Explicit addresses are hexadecimal. `--dry-run` shows the
symbolizer command, and symbolization has a 15-second deadline by default.

Keep the exact ELF from the failing run. A rebuilt kernel can assign different
addresses to functions. The current optimized OS build does not emit full source
debug information: symbol names can resolve, while source locations and inlined
frames may appear as `??`. The fault path resolves only the instruction
addresses the guest reports; Minyar failures also print their call chain, as
below.

### Interrupt handlers

An `interrupt function` is the real hardware entry on x86-64 and Arm64. The handler records work with `signalInterrupt`, and ordinary code
collects it with `takeInterrupt`:

```minyar
constant TICK = 0

interrupt function timerTick(vector: Integer) handles(32) {
    signalInterrupt(TICK)
}
```

The compiler checks the handler's whole call graph: it must be scalar and
acyclic, with no allocation, locks, blocking, native calls or floating point.
It then emits `irq_32`. That entry saves the registers it uses, counts the
interrupt, runs the handler, acknowledges the PIC (the slave PIC too for
vectors 40 to 47) and returns with `iretq`. The linker picks it over the weak
stub in `os/arch/x86_64/boot/entry.S`; unbound vectors keep the stub.
Acknowledging the device itself, such as reading the RTC's Register C, is port
I/O, so ordinary code does it after `takeInterrupt`.
`make check-osdev-irq-qemu` boots `os/tests/irq-kernel.min`. It checks the
linked entry's instructions, delivery, counting, and that code interrupted mid-loop
keeps its registers. On Arm64 the GIC entry in `os/arch/arm64/head.S` counts,
rearms the timer and sends the EOI as before. For IDs 16 to 1019 it also calls the
compiled `minyar_irq_dispatch`, after saving x5 to x30, ELR and SPSR. The same
test boots the Arm64 kernel, whose handler uses `handles(arch.TIMER)`.

### Recording and replaying a run

On Arm64, `--record FILE` makes `run`, `test` or `debug` write a replay log. A
later `--replay FILE` repeats that run exactly, instruction for instruction,
including when each interrupt arrived:

```sh
python3 tools/osdev.py test --arch arm64 --expect 'OSDEV IRQ PASS' --record build/irq.replay
python3 tools/osdev.py debug --arch arm64 --replay build/irq.replay
```

Replaying under `debug` lets a GDB with reverse execution step backwards from a
failure. Recording uses one CPU, single-threaded TCG, a virtual clock, disk
reads through QEMU's `blkreplay`, the network through `filter-replay`, and
seeded entropy. x86-64 is refused for now: its boot loader polls the ATA disk,
and under `blkreplay` those reads time out. `make check-osdev-replay-qemu`
checks that a replay of the IRQ kernel reproduces its serial log byte for byte.

### Kernel failure call chains

When kernel code stops, through `fail`, a failed check or a runtime range
error, the guest prints `Minyar stopped:` with the message, then
`Minyar stack trace:` and one return address per frame, innermost first:

```text
Minyar stopped: OSDEV PANIC EXPECTED
Minyar stack trace:
  at 0x1003bd
  at 0x100375
  at 0x100565
  at main (os/tests/panic-kernel.min:9:10)
```

`run` and `test` then map those addresses to Minyar functions using the kernel
ELF, and `symbolize --log` does the same for a saved log:

```text
osdev: Minyar stack trace, symbolized with build/os/x86_64/kernel.elf:
  at descend (os/tests/panic-kernel.min:4:10)
  at main (os/tests/panic-kernel.min:9:10)
```

Each frame names its function and the line where that function is declared, as
hosted traces do. The kernel needs no symbol table or unwinder for this:
freestanding builds keep frame pointers, and the runtime follows that chain
only when it fails. Keeping frame pointers costs one register in every kernel
function. Functions that link-time optimization inlines have no frame of their
own, so they don't appear. Runtime helpers have no Minyar name and are left
out. `make check-osdev-panic-qemu` checks the chain on x86-64 and Arm64.

For a deliberate Arm fault with a real instruction address, build and run the
expected-failure fixture, then symbolize its log before rebuilding the kernel:

```sh
python3 tools/osdev.py test --arch arm64 \
  --kernel-source os/tests/fault-kernel.min \
  --expect 'OSDEV FIELDS PASS' --log build/os/arm64/osdev-fault.log
python3 tools/osdev.py symbolize --arch arm64 --log build/os/arm64/osdev-fault.log
```

The first command must fail: the fixture reads an unmapped address. The second
resolves the fault PC to the retained `faultingRead` function in the matching ELF.
It is a postmortem symbol check, separate from the successful e1000 guest.

The e1000 driver also runs on the host against a deterministic device model
(`make check-osdev-devices`): the production driver, PCI scanner and
`device.Memory` code with only the machine and architecture modules replaced.
A seeded fault campaign lets a `simulation.World` choose delayed, reordered and
duplicate completions, missed and spurious interrupts, and errored or oversized
multi-descriptor receive frames. Each seed replays the same transcript, so a
failure names a seed you can rerun. It found the driver delivering malformed
frames, including the tail of an oversized frame (Linux CVE-2009-4536).

The virtio block driver gets the same treatment (`make check-osdev-virtio`): the
production `os/shared/virtio` transport, block driver and PCI scanner run
against a modeled virtio 1.x PCI disk. Its World delays completions and injects
spurious completions for chains the driver did not offer, short completions and
I/O errors. Every seed must read the disk image exactly or stop the driver; it
found the driver returning bytes the device never wrote (it trusted any used
entry and ignored the written length, the class Linux fixed by validating used
ids and lengths for untrusted hosts). The driver now checks both.

The e1000 driver uses explicit full `machine.fence()` barriers before enabling
the initial receive ring, after observing DMA completion, and before publishing
a tail to the device. These order normal RAM and device registers; volatile
accesses alone do not. Virtio acquires the
used-ring entries after observing a changed used index. The finite Arm guest
waits for actual e1000 transmit completion and reads the OS disk directory over
virtio; `OSDEV DMA PASS` precedes its final success line. These QEMU checks
exercise the protocol, while hardware ordering still follows the architecture
and coherent-memory assumptions of the current OS mappings. On Arm,
`machine.fence()` emits full-system DMB SY, beyond LLVM's inner-shareable
inter-thread fence. These full fences are stronger than the
minimum target-specific acquire/release barriers and carry that runtime cost.
