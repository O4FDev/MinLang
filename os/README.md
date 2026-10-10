# Minyar OS

An operating system for x86-64 PCs and 64-bit Arm whose boot loader, kernel,
drivers, network stack and desktop are written in Minyar. The desktop is a
faithful copy of the "ghost" agent interface from the reference recording,
measured frame by frame, and its agent talks to
[Atacama](../../atacama-discord-bot) over the machine's own TCP/IP stack.

```sh
make -C os                 # x86-64: build/os/x86_64/minyar-os.img
make -C os ARCH=arm64      # 64-bit Arm: build/os/arm64/kernel.elf and minyar-os.img
make -C os release         # both
make -C os run ARCH=arm64  # boot it in QEMU
```

Needs Homebrew LLVM (`brew install llvm lld`) and QEMU (`brew install qemu`).
The compiler builds on first use. On an Arm Mac the arm64 build runs under
Apple's hypervisor at the processor's own speed; the x86-64 build is
emulated instruction by instruction.

## Two architectures, one source tree

As in Linux, what differs between processors lives in `arch/`, and
everything else is shared. Each architecture has the same `arch` package
([`arch/x86_64/arch.min`](arch/x86_64/arch.min),
[`arch/arm64/arch.min`](arch/arm64/arch.min)): interrupt controller and timer,
clock calibration, starting and waking other processors, PCI configuration
access, and constants saying which hardware to expect. The build puts
`os/arch/$(ARCH)` first on the compiler's package path, so generic code's
`use "arch" as arch` finds the right one, and on Arm puts
`library/arch/arm64` next, so `use "machine"` gets the Arm intrinsics.

Drivers are generic and bind to whatever the machine has, as Linux's do: the
PC's PS/2 keyboard, VMware pointer and ATA disk on x86-64; virtio keyboard,
tablet, disk and entropy source on Arm; the Bochs display and e1000 network
adapter on both. Where no firmware has given PCI devices their addresses (on
Arm), [`shared/pci.min`](shared/pci.min) assigns them.

| | x86_64 | arm64 |
|---|---|---|
| Machine | QEMU `pc` | QEMU `virt` |
| Boot | BIOS, boot record, stage-two loader | QEMU loads `kernel.elf` directly |
| Interrupts and timer | 8259 PICs, PIT, HPET-calibrated TSC | GICv3, architectural timer |
| Other processors | INIT/SIPI through the local APIC | PSCI `CPU_ON` |
| PCI configuration | ports `0xCF8`/`0xCFC` | ECAM |
| Disk, input | ATA, PS/2, VMware pointer | virtio-blk, virtio-keyboard, virtio-tablet |
| `randomBytes()` | `RDRAND` | pool filled from virtio-rng |

## What happens at boot

On x86-64:

1. **Boot record** ([`arch/x86_64/boot/mbr.S`](arch/x86_64/boot/mbr.S), 512
   bytes of assembly). The BIOS loads it at `0x7C00`. It records the E820
   memory map, reads the stage-two loader to `0x10000`, identity-maps the first
   4 GiB with 2 MiB pages, enables SSE and long mode, and jumps to the loader.
   This is the only real-mode code.
2. **Loader** ([`arch/x86_64/loader/`](arch/x86_64/loader/), Minyar). Scans
   PCI, sets the display to 1720 × 1080 × 32 through the Bochs VBE registers,
   starts the timer, reads the disk directory with its own ATA driver, renders
   the boot screen with the TrueType renderer, loads `kernel.elf`, places its
   segments and jumps to it.

On Arm, QEMU loads `kernel.elf` at `0x4008_0000` and starts it in EL1 with the
MMU off; [`arch/arm64/head.S`](arch/arm64/head.S) clears `.bss`, builds
identity page tables, turns on the MMU, caches and FP/SIMD unit, installs the
exception vectors and calls the kernel.

Then, on both, the **kernel** ([`kernel/`](kernel/), Minyar) assigns PCI
addresses if needed and brings up the display, interrupts, disk, fonts,
keyboard and pointer, the e1000 network adapter, DHCP, the other processors
and the desktop, then runs one loop: poll the network, advance the agent,
redraw what changed, sleep until the next timer tick.

The disk image is built by [`tools/mkimage.min`](tools/mkimage.min), a hosted
Minyar program: boot record, loader, a directory of 64-byte entries, and the
files (`kernel.elf`, the Archivo fonts, `config.txt`). The Arm disk has an
empty boot record and no loader; its directory and files are the same.

## Layout

| Path | Contents |
|---|---|
| `arch/x86_64/` | Boot record, 64-bit entry and interrupt stubs, linker scripts, the stage-two loader and boot screen, and `arch.min` |
| `arch/arm64/` | Entry, page tables and exception vectors (`head.S`), linker script, and `arch.min` |
| `shared/` | Code used by both loader and kernel: PCI, display, interrupts and time, ATA, disk directory, parallel jobs |
| `shared/virtio/` | Virtio over PCI: block, input and entropy devices |
| `shared/graphics/` | Canvas, anti-aliased path rasterizer, TrueType fonts (glyf, cmap, GPOS kerning), wordmark |
| `kernel/input/` | Keyboard and pointer: PS/2 and the VMware/QEMU absolute pointer, or virtio input |
| `kernel/net/` | e1000 driver; Ethernet, ARP, IPv4, ICMP, UDP, DHCP, DNS, TCP; HTTP/1.1; JSON |
| `kernel/system/` | Starting the other processors and running work on them |
| `kernel/ui/` | The desktop: theme, typography, icons, conversation, composer, task window, pages, overlays |
| `kernel/agent/` | The agent: the moving-day task and the Atacama client |
| `assets/fonts/` | Archivo (SIL Open Font License) |

Everything above the boot code (x86-64's boot record, entry stub and
interrupt stubs; Arm's `head.S`) is Minyar. The language runtime underneath it
is the standard Minyar runtime built freestanding; see
[freestanding programs](../docs/freestanding.md).

## Using it

Type in the composer and press Enter. Requests that mention moving (or
"demo") run the task from the recording: the agent reads a ranked list of
movers on sfgate.com, visits their sites, builds a Google Sheet, phones each
company, and recommends one; those sites are drawn, not fetched.

Every other question is researched for real. The agent resolves
`en.wikipedia.org` with its own DNS client, opens a TLS 1.3 connection
(the `tls` and `crypto` packages, with keys from `RDRAND`) over its own TCP
stack, searches Wikipedia, opens and reads the best article in the task
window, asks Atacama, and answers with both, citing the article.

- The mouse needs no grab: QEMU reports the host pointer position directly.
- Mouse wheel, Page Up/Down and the arrow keys scroll the conversation.
- Click a step summary to show or hide the agent's steps.
- The task window's corner button maximizes it; the pause button pauses the
  agent; the call card's red button hangs up the current call.
- The copy button under an answer copies it; Notes lists finished answers.
- The sidebar's Tasks, Library, Notes and Search views, the help button (or
  F1), the account badge and the device in the corner open their own views.

## Atacama

The guest reaches the host at `10.0.2.2` through QEMU's user network, so run
the Atacama inference server on the host's port 8080:

```sh
~/.cache/atacama-local/start.sh
```

Settings are written into the image as `config.txt`:

```sh
make -C os ATACAMA_HOST=10.0.2.2 ATACAMA_PORT=8080 ATACAMA_KEY=minyar-local
```

The agent sends `POST /ask` with the question and a bearer token, shows the
exchange in the task window, streams the answer into the conversation and
lists any Wikipedia sources. The system window (click the device in the
corner) shows the network configuration and the result of the `/health`
check made at start-up.

## Display

The desktop renders 1720 × 1080 logical pixels, the reference's layout, which
has the same shape as a 14-inch MacBook Pro screen below the notch. With the
patched QEMU below, `make run` and `tools/show.sh` open it in macOS full screen
scaled to fit. Stock QEMU's Cocoa display scales partial updates separately,
which leaves faint seams, so with stock QEMU they use `zoom-to-fit=off` and the
window shows the guest's pixels 1:1 (half size on a Retina screen).

Stock QEMU's Cocoa display draws its window with Core Graphics on its main
thread, which also handles input. On a wide-gamut Mac display a full 1080p
frame costs that thread tens of milliseconds, so the pointer and animations
judder, and when macOS discards the window's contents (display sleep, screen
lock, another window on top) the window stays dark gray until each part of
the screen happens to change. `tools/build-qemu.sh` builds QEMU 11.1.2 with
`tools/qemu/cocoa-layer.patch`, which hands each frame to the window server
as an IOSurface instead: the GPU composites it and the window keeps its
contents. It builds both `qemu-system-x86_64` and `qemu-system-aarch64`;
`tools/show.sh` (with `ARCH=arm64` for the Arm build) and `make run` use it
when it exists.

The display driver pads each framebuffer row (a 2048-pixel pitch for 1720
visible pixels) so a frame is a whole number of 16 KiB pages: QEMU with
Apple's hypervisor tracks framebuffer writes in host pages and stops with an
assertion if a display's frame ends inside one.

For stock QEMU, the kernel copies the whole finished frame to the framebuffer
every five seconds, in time the frame leaves free, so a gray window heals.
Each copy makes stock QEMU redraw the whole window, a visible hitch, which is
why it is not done more often. `tools/show.sh` disables QEMU's App Nap and
starts it in a detached session so closing the launching terminal or test
tool does not terminate the VM.

## Rendering

Drawing is immediate-mode with damage tracking: anything that changes marks a
rectangle, and each frame redraws only those rectangles, clipped, then copies
them to the framebuffer. Conversation blocks render their static parts once
into their own bitmaps and are blitted; only animated parts (shimmering status
lines, the call waveform and timer, streaming text) are drawn every frame.
Glyphs are rasterized once per quarter-pixel position and cached, and printable
ASCII shapes through precomputed advance and kerning tables. Pages that never
change are rendered at both task-window sizes at start-up, so maximizing is a
copy; live pages are painted a strip at a time, a strip being started only
when its recent cost fits the time left in the frame. Frames target every 8 ms,
and the time a frame leaves goes to warming glyph caches and painting pages
ahead of need. With
`--freestanding` builds the profiler prints a per-component frame breakdown to
the serial console every five seconds. On x86-64 the kernel calibrates its TSC
against the PC HPET at startup: delivered PIT interrupt counts are not a wall
clock under emulation, and previously overstated FPS while slowing animations.
The PIT wakes halted CPUs at 250 Hz; active animation uses the TSC deadline.
Machines without the standard HPET use a logged PIT calibration fallback. On
Arm the architectural counter's frequency is published, and the virtual timer
provides the 250 Hz tick.

`profile:` measures drawn frames, while `cadence:` reports all frame-loop
iterations, missed 8 ms slots, the worst start gap, and complete work including
background painting and display refresh. The desktop redraws only damage:
an idle caret drawing about twice a second is intentional, not a 2 FPS limit.
Neither counter proves physical display presentation rate. Host load can
still cause individual late frames even when sustained animation exceeds
120 FPS.

## Reproducible input and display checks

`python3 tools/qemu-drive.py scenario.json` boots a headless test VM of the
`MOS_ARCH` build (`x86_64` by default, or `arm64`). A scenario
is an array of actions such as `["type", "moving demo"]`, `["key", "ret"]`,
`["click", 1683, 538]`, `["sweep", 100, 100, 1600, 900, 3]`, `["wait", 2]`,
and `["shot", "result"]`. A key may also be a chord, for example
`["key", ["ctrl", "backspace"]]`. Wait for queued input and animation to
settle before asserting screenshot contents.

Set `MOS_ATTACH=/tmp/minyar-visible-qmp.sock` to drive the visible VM started
by `tools/show.sh`. Only one QMP client can attach at a time. `MOS_OUT` selects
the screenshot directory; `MOS_SERIAL` selects the headless serial log;
`MOS_QEMU` can override the headless CPU/accelerator flags. Actions are logged
with host timestamps. QMP failures and timeouts fail the test instead of
silently ignoring input. `["window", "result"]` captures the actual macOS
window when `MOS_WINDOW` contains its CoreGraphics window number.

For an idle-gray regression, capture the host window **before** sending any
input or requesting a QMP screendump: screendump itself updates QEMU's display
surface. Keep guest framebuffer and host window evidence separate, and
account for the host screenshot's ICC color profile when comparing pixels.
