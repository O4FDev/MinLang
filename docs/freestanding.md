# Freestanding programs

Minyar can build programs that run with no operating system underneath them:
boot loaders, kernels and the [Minyar OS](../os/README.md) desktop. Two pieces
make this possible: the `machine` package, which reaches the hardware, and the
compiler's `--freestanding` mode.

## The `machine` package

```minyar
use "machine" as machine

machine.out16(0x01CE, 1)                 // an I/O port
let id = machine.read32(registers + 8)   // a memory-mapped device register
machine.fill32(framebuffer, 1720 * 1080, 0xF2F2F2)
```

Every function in [`library/machine.min`](../library/machine.min) is a compiler
intrinsic. A function whose body is `native "machine"` is not a call into C: the
compiler emits its LLVM IR inline, marks it `alwaysinline` and gives it no
call-depth or ownership frame, so `machine.load32(address)` costs exactly one
load. The intrinsics are:

| Group | Functions |
|---|---|
| Ordinary memory | `load8/16/32/64`, `store8/16/32/64`, `fill8`, `fill32`, `copy`, `address(bytes)` |
| Device memory | `read8/16/32/64`, `write8/16/32/64` (volatile), `fence` |
| I/O ports | `in8/16/32`, `out8/16/32` |
| Processor | `timestamp`, `pause`, `halt`, `enableInterrupts`, `disableInterrupts`, `waitForInterrupt`, `loadInterruptTable`, `interruptHandler`, `interruptCount`, `jump`, `hypervisorCall` |
| Multiple processors | `atomicAdd`, `callEntry`, `symbol` |
| Pixel loops | `blendSpan`, `blendMask` (blend 0x00RRGGBB pixels toward a color, uniformly or through a coverage mask), `coverage` (turn a row of float32 signed areas into coverage bytes) |

Addresses are Integers holding identity-mapped physical addresses.
`machine.address(bytes)` exposes the storage of a `Bytes` value so it can be
used for DMA or pixel buffers; it stays valid until the value grows, is cleared
or is released.

The pixel loops are written without overflow checks so LLVM can vectorize
them; they are what make anti-aliased filling and blending fast enough for a
frame every 8 ms.

The processor and port intrinsics in `library/machine.min` are x86-64
instructions. For 64-bit Arm, [`library/arch/arm64/machine.min`](../library/arch/arm64/machine.min)
has the same functions (`native "machine_arm64"`), with the processor ones as
Arm instructions (`wfi`, `msr daifclr`, `cntvct_el0`) and two more:
`timerFrequency()` and `firmwareCall(function, first, second, third)` for PSCI.
I/O ports, the x86 interrupt table and the VMware hypervisor call have no Arm
equivalent; they compile, so portable packages that offer them still build,
but stop the processor if reached. A build selects the Arm package by putting
its directory first on the package path:

```sh
build/minyarc kernel.min kernel.ll --library library/arch/arm64 --library library --freestanding
```

Unused intrinsics have internal linkage and disappear from programs that do
not call them.

## The `device` package

`machine` takes bare Integer addresses. [`library/device.min`](../library/device.min)
gives each kind of hardware location its own record type, so the compiler
rejects a port used as an address, a 16-bit register written as 32 bits, or a
raw Integer where a register belongs:

```minyar
use "device" as device

let window = device.registers(pci.memoryBar(card, 0), 0x20000)
let tail = device.register32(window, 0x3818)   // checked: in range, aligned
device.write32(tail, next)                     // checked: fits in 32 bits

let ring = device.allocate(1024, 4096)         // owns its storage
device.store64(ring, slot * 16, device.addressOf(buffers, slot * 2048))
```

`Registers` and `Register8` to `Register64` cover memory-mapped registers,
`Port8` to `Port32` I/O ports, and `Memory` DMA rings and buffers (from
`allocate`) or fixed physical ranges (from `physical`), with `view` for a
sub-range, `copy`, `fill` and `write` for bulk transfers, and `inBlock16` for a
block from a port such as a disk sector. A location is checked once when it is
made; later accesses cost the instruction and one field load. Accesses are
volatile. Ordinary calls carry Minyar's call-depth and ownership frames (a
function that calls no other Minyar function has no call-depth frame), so a
loop over thousands of values should use a block transfer instead.

Every driver in Minyar OS (PCI, display, ATA, keyboard and mouse, interrupt
controllers, timer, HPET, APIC start-up, e1000) and the loader's kernel
placement use `device`. `machine` remains for processor instructions, pixel
loops and other plain memory the program owns, the clock words read every
frame, and parallel functions, which cannot take records.

Every field is [`private`](language.md#records), so these values come only from
the package's functions: a program cannot build a `Register32` from an Integer
or reach the Bytes behind a `Memory`. `device.base(window)` and
`device.size(memory)` read what callers need.

## `--freestanding`

```sh
build/minyarc kernel.min kernel.ll --library library --bounded-owners 32 --freestanding
```

`--library` may be given more than once: packages are looked up in each
directory in order, so an earlier directory can replace a package, as
`library/arch/arm64/machine.min` replaces `library/machine.min`.

Interrupts on x86-64 push their frame onto the current stack, so freestanding
code may not keep data in the 128 bytes below the stack pointer.
`--freestanding` marks every function `noredzone`; with that, a kernel can run
with interrupts enabled all the time. The 64-bit Arm calling convention has no
red zone.

## The runtime

[`runtime/freestanding`](../runtime/freestanding/) builds the standard runtime
for bare metal. `runtime.c` is the usual configuration;
`freestanding.c` and `include/` provide the small part of the C library the
runtime uses: a size-class allocator over the linker's `__heap_start` to
`__heap_end` region, memory and string functions, `printf`-family formatting,
`strtod`, the mathematics functions LLVM lowers `sin`, `exp` and friends to,
and `stdout`/`stderr` on the first serial port (the PC's COM1 or the Arm
board's PL011). On x86-64 `exit` reports its status to QEMU's `isa-debug-exit`
device and halts; on Arm it powers off through PSCI. Decimal conversion needs
more precision than a double: the x87's 80-bit `long double` on x86-64, and a
pair of doubles kept exact with fused multiply-add on Arm, where `long double`
is a 128-bit software type. `randomBytes()` uses `RDRAND` on x86-64; Arm
processors such as Apple's M1 have no random instruction, so there the runtime
draws on a pool the program fills (Minyar OS uses a virtio entropy device).

The runtime is linked as LLVM bitcode with its per-function CPU attributes and
`no-builtins` removed, exactly like the hosted LTO build, so its hot paths
inline into generated code. Its `memcpy`, `memmove` and `memset` are the
compiler builtins, so fixed-size copies such as a `Float32` read stay single
loads instead of calls. The C library shim keeps `no-builtins` so its
`memcpy` is never compiled into a call to itself.

A freestanding program provides its own entry: see
[`os/arch/x86_64/boot/entry.S`](../os/arch/x86_64/boot/entry.S), which clears
`.bss`, sets up a stack and calls `main`, its Arm counterpart
[`os/arch/arm64/head.S`](../os/arch/arm64/head.S), which also builds page
tables and turns on the MMU and caches, and [`os/Makefile`](../os/Makefile) for
the complete build of either.

## Multiple processors

Minyar OS starts every processor QEMU provides. On x86-64 (`-smp 4 -accel
tcg,thread=multi` gives each its own host thread) the `arch` package copies the
trampoline from `entry.S` to `0x8000` and sends INIT and start-up IPIs; on Arm
it calls PSCI `CPU_ON` for each. Each processor runs `worker` in
[`kernel/system/processors.min`](../os/kernel/system/processors.min), a
[parallel function](language.md#parallel-functions) that sleeps (`hlt`, or `wfi` on Arm) until a
wake-up interrupt announces a job. `processors.parallelFor(processors, entry, count,
arguments)` runs a parallel function for every item in `0..count`, items being
claimed with `machine.atomicAdd`; the boot processor works too, and the call
returns once every processor has acknowledged the job. The desktop's working
glow is drawn this way, sixteen rows per item.
