# Native mobile apps

Minyar compiles ordinary source to target LLVM code. UIKit supplies the iOS
application lifecycle and native controls. Android's NDK supplies a core
static library that a Java or Kotlin application can call through JNI.
These are 64-bit targets: iOS device arm64, Simulator arm64 or x86_64, and
Android arm64-v8a or x86_64. The current minimums are iOS 16 and Android API 28.

## An iOS application

Install full Xcode, select it with `xcode-select`, and install a Simulator
runtime in Xcode. The normal Minyar host compiler still uses the repository's
pinned LLVM toolchain. Build the example from the repository root:

```sh
python3 tools/mobile.py examples/mobile-hello/main.min --target ios-simulator
```

The result is `build/mobile/ios-simulator/Minyar.app`, signed ad hoc for the
Simulator. `--arch arm64` or `--arch x86_64` chooses a Simulator architecture;
the default matches the Mac. `--debug` selects O0 instead of O2. `--name`,
`--identifier`, `--minimum-ios`, `--library` and `-o` customize the build.
The output must end in `.app`; replacing an existing unrelated app is rejected.

With a Simulator already booted, install and launch it:

```sh
xcrun simctl install booted 'build/mobile/ios-simulator/Minyar.app'
xcrun simctl launch booted 'org.minyar.hello'
```

For a device executable, use the device SDK:

```sh
python3 tools/mobile.py examples/mobile-hello/main.min --target ios-device
```

This produces an **unsigned** arm64 bundle. Before device installation, an
Apple development identity must sign it, and its embedded provisioning profile
must cover the device, team, bundle identifier and entitlements. The builder
does not create certificates, profiles or distribution signing permissions.
Use the same identifier in the build and the profile. Simulator ad hoc signing
does not authorize device installation. This slice supplies a UIKit host;
a SwiftUI host and an Xcode project exporter are future work.

## One view model for desktop and mobile

[`ui`](../library/ui.min) describes rows, columns, labels, headings, keyed
buttons, inputs and toggles using ordinary records and functions.
[`ui-ios`](../library/ui-ios.min) renders those descriptions with UIKit;
`ui-macos` renders the same descriptions with AppKit. The
[hello application](../examples/mobile-hello/main.min) keeps its model in
Minyar, builds a view from it, and updates the model from keyed events.

`ui-ios.run(title, view, update)` calls `view()` on launch and after each
event. The `update` callback receives a `mobile.Event`:

| Field | Meaning |
| --- | --- |
| `kind` | `mobile.ACTION` (1), `mobile.CHANGE` (2), or `mobile.SUBMIT` (6) |
| `key` | The control's unique key |
| `text` | Input text for input changes/submission; empty for buttons and toggles |
| `checked` | The current switch state for a toggle change; false otherwise |

Descriptions are validated before rendering: at most 1024 nodes, at most 64
levels, unique control keys, and the shared `ui` spacing/padding rules.
Compatible descriptions keep their UIKit controls, keyboard focus and clamped
UTF-16 editing selection. In-progress IME marked text remains native until
composition ends. A change to kind, key, parent or child structure rebuilds
the native tree. Layout uses safe areas, keyboard avoidance, scrolling and
Dynamic Type; row and column spacing/padding are measured in UIKit points.

UIKit owns the main loop. `mobile.run` is a blocking call from the ordinary
generated Minyar entry; the entry initializes arguments and globals normally.
It keeps the application's callback and captured model alive. Native event
callbacks run synchronously on that same main thread and execution domain;
the bridge checks the domain and retains the selected callback for the call.
Native descriptors own copies of text, and event results are owned Minyar Text.
No borrowed Text pointer is saved after its call returns. Idle cleanup uses a
run-loop observer and a one-shot timer only while reclamation work remains.

The low-level `mobile.begin/node/end` boundary is available for renderers.
It is iOS-specific today. It uses the existing native ABI and introduces no
language syntax. An app may start UIKit once; `mobile.run` normally never
returns. Slow work in its callbacks blocks the UI thread.

## Android core code through the NDK

Install an [official Android NDK](https://developer.android.com/ndk/downloads/)
and set `ANDROID_NDK_HOME` to its root. The builder uses the NDK target Clang,
headers, libraries and archiver separately from the pinned Minyar host compiler:

```sh
python3 tools/mobile.py examples/mobile-hello/android/main.min --target android-arm64
python3 tools/mobile.py examples/mobile-hello/android/main.min --target android-x86_64
```

Each target produces `build/mobile/TARGET/libminyar-app.a` and a sibling
`libminyar-app.a.json` build record. The archive contains PIC program/runtime
objects and `int minyar_mobile_entry(void)`. Call that entry once; it runs
ordinary Minyar startup and cleanup and returns the entry's signed 32-bit
result. Later or concurrent startup attempts return -1. This is a startup
boundary, not an API for calling arbitrary Minyar functions or passing managed
values between Java threads. API 28 is required by the runtime's `getrandom`
path. `--api` can raise the minimum.

The [Android sample](../examples/mobile-hello/android) contains a Minyar program
returning 42, a JNI adapter, a native Activity and CMake configuration. In an
Android Studio Java Views project with package `org.minyar.hello`:

1. Use API 28 or later as the minimum SDK. Copy `MainActivity.java` into the
   package source directory; keep the project's normal launcher manifest entry.
2. Copy `minyar-jni.c` and `CMakeLists.txt` into the app's native source directory.
   Configure `externalNativeBuild.cmake.path` to this CMake file.
3. Pass `-DMINYAR_ARCHIVE=/absolute/path/to/libminyar-app.a` to CMake for the
   matching ABI, and set the Gradle `abiFilters` to that ABI. Building both ABIs
   needs one matching archive path per ABI; a single path cannot serve both.
4. Build/install with Android Studio. The Activity displays the Minyar result
   and retains it across Activity recreation within the same process.

For example, an arm64-only Gradle configuration uses
`abiFilters 'arm64-v8a'` and a CMake argument selecting the `android-arm64`
archive. CMake hides the imported runtime symbols, exports the JNI entry,
requires all symbols to resolve, and requests 16 KiB ELF page alignment.
The NDK [other build systems guide](https://developer.android.com/ndk/guides/other_build_systems)
describes target Clang selection; the
[JNI guide](https://developer.android.com/training/articles/perf-jni)
describes the Java/native boundary.

If extending the adapter to return text, transfer UTF-8 as a Java byte array
and decode with `StandardCharsets.UTF_8`. JNI `NewStringUTF` accepts modified
UTF-8, which is not the Minyar Text representation. Never expose a managed
pointer as a Java-owned value. Android source traces currently fall back to
the Minyar entry location because the runtime's Linux symbol reader inspects
the executable rather than the JNI shared library.

Android support here is core-code embedding. It does not include an Android
renderer for `ui.View`, a Gradle project generator, or emulator qualification.
Native package providers other than the core runtime are rejected; UIKit's
`mobileios` provider is accepted only for iOS. Managed thread entries, raw
machine intrinsics and C-layout adapters are rejected by this builder until
their target-specific support is implemented.

## Verification

`make check-mobile` runs target/SDK selection and output protection cases plus
the real Minyar callback bridge at O0/O2 with eager and system ownership.
`make check-mobile-sanitize` repeats those four bridge variants under
ASan/UBSan, with exact Unicode events, captured-state updates, copied native
snapshots and final ownership assertions. The native fixture supplies a fake
host; these portable checks do not prove UIKit layout or device execution.

`make check-mobile-ios` cross-compiles and links the actual hello application
with both Xcode SDKs. It never boots a Simulator. `ANDROID_NDK_HOME=... make
check-mobile-android` builds both Android archives and links the actual JNI
adapter with no undefined symbols, verifies ELF architectures and checks that
the generated `main` is hidden. It does not execute an Android device.

All target objects are rebuilt in an isolated staging directory. A host
runtime object is never linked into a mobile target. Successful build records
include target triple, SDK, compiler, source/IR/runtime hashes and native
providers. Builds need Python 3.9+ and the ordinary repository build tools.
On a shared machine, follow its build-host policy; moonshot-day local work uses
the coordination `lx` wrapper, and portable checks use `bx mobile`.
