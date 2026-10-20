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

## Shared views on Android

[`ui-android`](../library/ui-android.min) renders the same `ui.View` descriptions
as UIKit and AppKit. The [Android UI example](../examples/mobile-hello/android/ui.min)
uses the hello application's existing Minyar model. Build a matching core archive:

```sh
python3 tools/mobile.py examples/mobile-hello/android/ui.min --target android-arm64 -o build/mobile/android-arm64/libminyar-ui.a
```

In an Android Studio Java Views application with namespace/application ID
`org.minyar.hello` and minimum SDK 28:

1. Copy `MinyarActivity.java` and `MinyarSnapshot.java` from the Android sample
   into the Java package. Use `ui/AndroidManifest.xml` as the launcher manifest;
   remove the old Activity launcher entry.
2. Point `externalNativeBuild.cmake.path` at the sample's `ui/CMakeLists.txt`.
   Pass `-DMINYAR_ROOT=/absolute/path/to/Minyar-Lang` and
   `-DMINYAR_ARCHIVE=/absolute/path/to/libminyar-ui.a`. Select the matching
   `abiFilters` entry, as with the scalar sample above.
3. Build/install through Android Studio. Keep the Minyar checkout at the version
   used to build the archive; its build record hashes the required JNI provider
   source and headers. The CMake project compiles that provider directly and
   hides the imported core archive's symbols.

`ui-android.run(title, view, update)` receives an `android.Event` with the same
`kind`, `key`, `text` and `checked` fields as `mobile.Event`. The Activity creates
one Java worker thread that enters ordinary Minyar startup. `android.run` blocks
on that worker, keeping its callback and model alive. Only the worker accesses
managed values or services ownership cleanup. Android's UI thread renders copied
descriptions and submits copied standard UTF-8 byte arrays through JNI. JNI
Modified UTF-8 and managed pointers never cross this boundary.

The worker lives for the process lifetime. Stopping/recreating the Activity
detaches its binding without stopping the model. A new Activity attaches to the
latest snapshot; an old binding cannot submit new events or detach its successor.
Already admitted events remain ordered across detachment. A queued event whose
control identity has disappeared is acknowledged without dispatching to another
control. Inputs/toggles keep newer admitted edits while an older snapshot is in
flight. Compatible controls keep their native instances; input replacement
preserves clamped UTF-16 selection and defers changes during IME composition.

Android snapshots have the shared 1024-node/64-level bounds plus a 1 MiB encoded
frame limit, 16 KiB UTF-8 per text value and 256 bytes per key. The native event
queue holds at most 64 events and 256 KiB of payload. Admission never waits for
capacity: a rejected edit/action displays a message asking the user to retry.
Snapshots may coalesce; admitted events do not. Slow callbacks delay rendering
and can fill the queue. No repeating UI polling timer runs while idle.

The source and host tests provide an Android renderer, not device qualification.
Actual Android layout, input methods and lifecycle behavior still need a device
or emulator run. No Gradle project generator is supplied. Core runtime and the
platform's own UI provider are the supported native packages; `mobileios` belongs
to iOS and `mobileandroid` to Android. Managed thread entries, raw machine
intrinsics and C-layout adapters remain unsupported by this builder.

## Verification

`make check-mobile` runs target/SDK selection and output protection cases plus
the real Minyar callback bridge at O0/O2 with eager and system ownership.
`make check-mobile-sanitize` repeats those four bridge variants under
ASan/UBSan, with exact Unicode events, captured-state updates, copied native
snapshots and final ownership assertions. The native fixture supplies a fake
host; these portable checks do not prove UIKit layout or device execution.
Portable mobile checks also exercise Android's production copied transport at
O0/O2; the sanitizer target checks its native allocations and cleanup.

`make check-mobile-ios` cross-compiles and links the actual hello application
with both Xcode SDKs. It never boots a Simulator. `ANDROID_NDK_HOME=... make
check-mobile-android` builds both Android archives and links the actual JNI
adapter with no undefined symbols, verifies ELF architectures and checks that
the generated `main` is hidden. Both the scalar and shared-view providers are
linked for both Android ABIs. It does not execute an Android device.

With a JDK, `make check-mobile-android-host` runs the production JNI provider and
actual hello model on a Java-created worker in a desktop JVM, at O0/O2 for eager
and system ownership. The test checks Unicode copies, model events, rebinding,
one-shot startup and complete worker-domain ownership cleanup. The explicit
`check-mobile-android-host-sanitize` target adds ASan/UBSan on Linux x86_64.
`ANDROID_JAR=/path/to/android.jar make check-mobile-android-java` checks the wire
decoder and compiles the actual Activity against the installed Android API.
These checks do not substitute for running Android's UI.

`make check-mobile-ios-smoke-build` builds a test-only app using the real
UIKit adapter and the real hello model. On an already booted iOS Simulator,
`MINYAR_SIMULATOR_UDID=... make check-mobile-ios-simulator` installs and runs it.
The app checks launch, button action, Unicode editing, switch changes, native
control reuse, selection preservation/clamping and basic layout, then exits.
This explicit target never boots a Simulator and is excluded from automatic
gates. It retains current-attempt install/launch stdout, stderr, commands and
terminal status/timeout metadata in `build/mobile-tests/ios-smoke`, including
failed installation and partial output from a timed-out launch.

All target objects are rebuilt in an isolated staging directory. A host
runtime object is never linked into a mobile target. Successful build records
include target triple, SDK, compiler, source/IR/runtime hashes and native
providers. Builds need Python 3.9+ and the ordinary repository build tools.
On a shared machine, follow its build-host policy; moonshot-day local work uses
the coordination `lx` wrapper, and portable checks use `bx mobile`.
