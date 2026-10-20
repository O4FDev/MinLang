# Developing a kernel

`tools/osdev.py` builds with the existing `os/Makefile` and starts QEMU with the
same hardware devices. It runs on Linux and macOS with Python 3.9 or later,
LLVM (`clang`, `ld.lld`, `llvm-objcopy`), Make and QEMU installed. The compiler
is built by the Makefile when needed. The commands below run from the repository
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
uses the directory of `clang` on `PATH`. The existing Makefile's recipe paths
are not fully quoted, so actual builds require a checkout path without spaces.
Already-built images can be run from paths with spaces or commas.

## Finite kernel tests

Use a kernel that prints a unique success line, then exits with status zero:

```sh
python3 tools/osdev.py test --arch arm64 \
  --kernel-source os/tests/fields-kernel.min \
  --expect 'OSDEV FIELDS PASS' --timeout 30
```

`make check-osdev-qemu` runs this Arm test; `OSDEV_ARCH=x86_64` selects the
PC boot path. The Arm guest exercises PCI discovery, the real e1000 driver's
packed descriptors and checked TCTL fields, then exits. The legacy QEMU e1000
does not emulate TIPG; its exact register bytes are checked by the host suite.
The x86 loader currently stops in its pre-existing wordmark/graphics path with
a NaN conversion failure on the Linux emulation box. The wrapper reports that
failure; use the Arm test for the verified finite path while it is investigated.

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
Builds have their own 600-second deadline (`--build-timeout`). The wrapper
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
frames may appear as `??`. This workflow does not reconstruct a stack or add
compiler debug metadata. It resolves the instruction addresses the guest reports.

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
