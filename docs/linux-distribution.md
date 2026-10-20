# Linux distributions

`make package-linux` builds a native release containing Minyar, its standard
library, LLVM 23.1.3, Clang resource headers and the matching LLD linker. Running
the release does not need Make, Python, zsh or an existing LLVM installation.
The build host needs Python 3.9+, Make, zsh, binutils and native LLVM 23.1.3.

The initial runtime contract is glibc 2.39 or newer, with the build's OS runtime
libraries and C development files installed. Ubuntu 24.04 ARM64 is the initial
qualification environment. This is not a musl/Alpine release or a universal
Linux binary. On Ubuntu 24.04 the runtime prerequisites are:

```sh
sudo apt install build-essential libffi8 libedit2 libz3-4 zlib1g libzstd1 libxml2
```

The compiler and LLVM are private to the archive. The system supplies glibc,
libstdc++, libgcc and the libraries listed in `distribution.json`; their versions
and sonames remain part of the platform contract. A newer distribution with
different sonames needs its own qualification. The launcher checks architecture
and glibc before executing packaged binaries, and reports missing LLVM runtime
dependencies before the signed installer selects the toolchain. `minyar --doctor`
checks the installed C headers and a real opaque-IR/LTO build.

Build on the target architecture, without `-march=native`:

```sh
make package-linux MINYAR_VERSION=0.1.0 MINYAR_LLVM_ROOT=/usr/lib/llvm-23
tar -xzf build/releases/minyar-0.1.0-linux-arm64.tar.gz -C /tmp
make check-linux-distribution \
  MINYAR_DISTRIBUTION=/tmp/minyar-0.1.0-linux-arm64
```

The packager checks every bundled ELF's CPU, 64-bit layout, glibc symbol versions,
relative library search paths and shared-library names. LLVM's transitive shared
libraries must resolve inside the staged private toolchain. The archive includes
LLVM's license, a file-hash manifest and the OS shared-library requirements.
Existing versioned artifacts cannot be overwritten. These checks do not replace
running the result in a fresh supported OS image with no installed LLVM.

The distribution check exercises the signed loopback `curl | sh` installation,
fresh-home projects, debug/release and native builds, memory profiles, project
pins, self-update and relocation. It also checks that runtime commands never
start Make, Python or zsh. Pass `--paint /path/to/minyar-paint` directly to
`tests/linux-distribution.py` to verify the offline external gallery at O0/O2.
Nothing is installed globally or served beyond loopback.

Prepare the audited archive with the same [signed release workflow](install.md)
as macOS. Public hosting, release signing keys and publishing remain operator
decisions; the build and test commands do not publish anything.
