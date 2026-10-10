# Native Linux desktop development

The experimental native compiler targets Linux through the same Minyar parser,
semantic compiler, SIL optimizer and LLVM backend as the macOS target. The Linux
SDK module imports GTK 4, libadwaita, GLib and GIO directly from system headers.
Calls use the libraries' C ABI. There is no JavaScript engine, web view, generated
Swift source, or Minyar UI interpreter in this path.

This is an early backend, not completed cross-platform UI parity. The SDK surface
is currently C-shaped: GObject ownership, signal callbacks and inheritance casts
are explicit. A declarative Minyar UI layer and generated ownership-aware GIR
bindings remain future work. Ordinary compilation still requires the Swift
runtime built with the compiler; "native" does not mean runtime-free.

## Development target

The initial development guest is Fedora 44 Workstation ARM64 in UTM: GNOME on
Wayland, 4 virtual CPUs, 8 GiB RAM and a **100 GiB sparse disk**. The disk grows as
needed; 100 GiB is its ceiling. GTK 4.22.5 and libadwaita 1.9.4 were installed from
Fedora's stable repositories. The existing Debian VM is separate.

Prepare a Fedora 44 checkout and build the pinned compiler:

```sh
./scripts/linux-desktop-setup.sh
python3 scripts/native-toolchain.py fetch
python3 scripts/native-toolchain.py native --jobs 4
make check-native-linux
```

Use fewer jobs if memory is constrained. This configuration builds a matching
Linux standard library and runtime, unlike the macOS configuration which uses
Xcode's installed SDK/runtime. A compiler development tree can grow considerably;
check available disk space before rebuilding additional configurations.

## Build an app

Run these commands **inside Linux**, from the repository:

```sh
./minyar --backend native --release --pkg-config libadwaita-1 \
  examples/native-editor -o build/minyar-editor
./build/minyar-editor --model-test
./build/minyar-editor
```

The last command needs a graphical desktop session. The current output is an ELF
executable linked to the installed SDK and compiler runtime. Use the experimental
Flatpak packager below to bundle those runtime libraries and a desktop launcher.

`--pkg-config` obtains the actual header and linker flags from the system SDK.
`use "LinuxDesktop"` exposes the native APIs through the compiler's Clang module
importer. SDK minimum versions are determined by the APIs used by the app; this
example uses modern GTK file dialogs and libadwaita alert dialogs.

A Mac cannot yet build this Linux target by adding `--target-platform linux`.
Cross-compilation also needs a target compiler configuration, Linux sysroot,
libraries and matching runtime. The launcher reports this explicitly instead of
producing a Mac binary with Linux source selection.

## One app, native implementations

```text
native-editor/
  app.min                         # app entry and shared model checks
  DocumentState.min               # shared text, dirty state and word count
  PlatformApplication.mac.min     # SwiftUI DocumentGroup and TextEditor
  PlatformApplication.linux.min   # libadwaita window, GTK text view and GIO
```

All selected files in an app share a module. Components need no file imports.
Every nested `app.min` starts another app and excludes that subtree from its
parent. Platform variants replace the corresponding base file; unrelated
platform variants never reach the compiler.

Build the same directory on macOS:

```sh
./minyar --backend native --release examples/native-editor \
  --bundle-id org.minyar.editor -o 'build/Minyar Editor.app'
```

The editor deliberately uses native document behavior on each platform. macOS
uses SwiftUI's document infrastructure, including system save/close behavior.
Linux uses GTK asynchronous file dialogs, GIO asynchronous file reads and writes,
and explicit save/discard/cancel handling. Linux currently presents a save dialog
on every save. File access uses GIO so a selected file can come from a portal or
remote provider. The SDK control build has also passed sandboxed Flatpak save and
open checks through GNOME's file portal, without general home-directory access.

This proves shared application logic and platform selection. It does not yet
prove a shared declarative UI syntax. Do not expose dummy implementations of
platform-only features just to make a program compile. Keep such code in its
platform implementation; handle runtime permission denial/cancellation as normal
results. Platform capabilities and their language syntax are still being designed.

## Validation

Current Linux validation is preliminary: the SDK control executable and its
Flatpak passed model, window/text-signal, save and open checks on Fedora 44.
The direct Minyar compiler build is still in progress; these control checks do
not establish that the original `.min` sources compile successfully on Linux.

`make check-native-linux` exercises original `.min` input, Linux file selection,
nested app boundaries, original-source errors, failed-build preservation, SDK
struct layout against a C control, GObject signal callbacks, shared document
logic, conditional binding mutability, generics/ARC/actors/Observation macros,
and an exported native shared library called from C.

From a graphical Linux session, `./build/minyar-editor --smoke` mounts a window,
checks GTK text signals against the shared model, then exits.

GUI verification also needs a real desktop: edit text, save, reopen, cancel file
selection, and close a dirty document using each confirmation response. VM
software rendering is not evidence of native GPU performance. No zero-overhead
claim follows from a successful build; ownership-safe bindings and representative
benchmarks remain necessary.

## Next milestones

- Generate ergonomic, typed SDK bindings from GIR ownership and nullability data.
- Design shared declarative components without hiding platform capabilities.
- Repeat the Flatpak and portal checks with the direct Minyar compiler output.
- Configure reproducible Linux sysroots for cross-compilation from macOS.
- Extend accessibility, input, lifecycle and performance coverage on real hardware.

## Experimental Flatpak packaging

Install `flatpak` and `patchelf`, then install `org.gnome.Platform//51` and
`org.gnome.Sdk//51` from Flathub in the development user's installation. The
packager accepts a trusted executable built locally; it is not a binary scanner
for untrusted downloads.

```sh
python3 scripts/linux-flatpak.py build/minyar-editor \
  --app-id org.minyar.editor --name 'Minyar Editor' \
  --icon examples/native-editor/assets/org.minyar.editor.svg \
  --license build/native-toolchain/swift/LICENSE.txt \
  -o build/minyar-editor.flatpak
flatpak install --user ./build/minyar-editor.flatpak
flatpak run org.minyar.editor
```

Supply additional `--license` arguments for the application and every bundled
dependency's required notices. The script bundles Swift/dispatch runtime
libraries, checks dynamic relocations against the selected GNOME runtime, and
only replaces the output bundle after successful export. It grants Wayland and
GPU access; file access goes through portals. It does not publish to Flathub.
This is an experimental local packaging path, not a reproducible SDK build or
a completed distribution workflow.
