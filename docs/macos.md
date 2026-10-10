# Native macOS applications

Minyar's `macos` package builds real AppKit applications. UI construction and
application behavior are written in Minyar and compiled to native LLVM code.
The package uses NSApplication, NSWindow, NSStackView, native controls, menus,
text editing, file panels and the system clipboard. No GLFW, web view, Swift
runtime, or handwritten foreign code is required in a Minyar application.

Requires macOS, Apple's command-line developer tools, and the ordinary Minyar
build prerequisites (including a working Python 3 for app packaging;
`MINYAR_PYTHON` can select an interpreter). GUI tests
and applications require a logged-in desktop session. Builds target the host
architecture and compiler's deployment target; the bundle records the actual
minimum OS version from the executable. Older macOS versions and Intel Macs
need separate testing; this feature was initially verified on Apple Silicon.

```sh
./minyar --app --bundle-id org.example.notes examples/macos/main.min -o "build/Minyar Notes.app"
open "build/Minyar Notes.app"
```

Use `--release` before the input filename for optimized builds. Without `--app`,
the same source builds a directly executable desktop program. `--app` appends
`.app` to the output name if needed, creates `Contents/MacOS/application` and
`Info.plist`, and applies and verifies an ad-hoc signature for local execution.
Use your own `--bundle-id` for each application; the default is
`org.minyar.application`. It is not a Developer ID distribution or notarization
workflow. Icons, entitlements, universal binaries and App Store packaging are
not supplied yet.

Existing Minyar-generated bundles can be rebuilt. The packager constructs and
signs a complete replacement before moving the old bundle aside, and restores
the old bundle if installation fails. A per-output lock prevents simultaneous
replacement. Unrelated directories, bundles, and symlink outputs are rejected.
A process killed during packaging can leave a `.minyar-lock` beside the app;
remove it only after confirming that no build is using it. If interrupted
during installation, the prior bundle may be preserved as
`.minyar-app-*/previous.app` beside the destination.

## Minimal application

```minyar
use "macos" as mac

mac.initialize("Hello")
let window = mac.window("Hello from Minyar", 480, 240)
let column = mac.column(window, 12)
mac.padding(column, 20)
let label = mac.label(column, "A native AppKit window")
let button = mac.button(column, "Say hello")
mac.show(window)
while mac.nextEvent(0.1) {
    if mac.eventType() == mac.ACTION && mac.eventSource() == button {
        mac.setText(label, "Hello, macOS!")
    }
    if mac.eventType() == mac.CLOSED {
        mac.quit()
    }
}
mac.destroy(window)
```

The [notes example](../examples/macos/main.min) includes a multiline editor,
Open/Save panels, Command-O/Command-S shortcuts, and status updates. For a
bounded launch that verifies the text bridge and exits:

```sh
"build/Minyar Notes.app/Contents/MacOS/application" --smoke
```

## API and object ownership

[The package source](../library/macos.min) documents every function and its
signature. All calls must run on the main thread after a single `initialize`.
AppKit objects are represented by checked, monotonically increasing Integer
handles. Arbitrary, stale, or incorrectly typed handles stop the program with a
Minyar diagnostic. IDs are not native pointers and are never reused. Handles
are process-local; do not serialize them or share them between processes.

| Area | Functions | Native API |
| --- | --- | --- |
| Application | `initialize`, `nextEvent`, `quit` | NSApplication and its delegate |
| Windows | `window`, `show`, `close`, `destroy`, `width`, `height` | NSWindow |
| Layout | `column`, `row`, `padding`, `size` | NSStackView, NSLayoutConstraint |
| Controls | `label`, `button`, `textField`, `textEditor`, `checkbox`, `slider`, `separator` | NSTextField, NSButton, NSTextView/NSScrollView, NSSlider, NSBox |
| Properties | `text`, `setText`, `enabled`, `checked`, `setChecked`, `value`, `setValue` | AppKit properties |
| Menus | `menu`, `menuItem` | NSMenu, NSMenuItem, target/action |
| Events | `eventType`, `eventSource`, `eventText` | Queued delegate and target/action events |
| System UI | `openFile`, `saveFile`, `alert` | NSOpenPanel, NSSavePanel, NSAlert |
| Clipboard | `clipboardText`, `setClipboardText` | NSPasteboard |

A window owns its entire control tree, including nested rows and columns.
Attach one root view to a window, then add controls to rows or columns. Layout
uses point units and Auto Layout. `size(view, width, height)` adds explicit
dimension constraints; zero removes the corresponding explicit constraint.
Text fields and editors also have minimum sizes. Avoid imposing contradictory
sizes on a root view pinned to its window.

`close` closes the native window and enqueues `CLOSED`; handles remain valid so
the application can inspect or save data, or show the window again. `destroy`
closes without another callback and invalidates the window and every descendant
handle. Pending events for destroyed objects are removed; the current event is
still a snapshot. Application menus live until process exit. Use `destroy` for
windows that are no longer needed; dropping the Integer variable alone does
not destroy the native window.

Native objects use Objective-C ARC. Every bridge call has an autorelease pool.
Input Text is borrowed only during the call and copied into NSString. Returned
Text is an independent owned Minyar allocation, including text read from events,
clipboard and file panels. UTF-8, supplementary Unicode characters and embedded
zero bytes in control text survive the boundary. Returned Text remains valid
after a control changes or its window is destroyed. All existing Minyar memory
profiles work; their pool limits apply to Minyar allocations, not AppKit's own
allocations. Desktop operations do not have bounded execution time.

## Event loop

`nextEvent(timeout)` dispatches AppKit input, updates windows and selects one
queued Minyar event. A timeout between 0 and 60 seconds returns true with `NONE`
when no application event arrived. Zero polls without waiting. Normally use
`0.1` to avoid busy-waiting while keeping application work responsive.

| Kind | Source | Text |
| --- | --- | --- |
| `NONE` | 0 | empty |
| `ACTION` | button, checkbox, or menu item | empty |
| `CHANGE` | text field, editor, or slider | text snapshot for editors; empty for sliders |
| `CLOSED` | window | empty |
| `RESIZED` | window | empty |
| `QUIT` | 0 | empty |

Read checkbox and slider state with `checked` and `value`. Programmatic property
setters do not generate user actions. Consecutive text changes or resizes for
the same source are coalesced to the latest snapshot. The queue holds at most
4096 events and stops with a diagnostic on overflow rather than silently losing
action events. The event source is valid unless the application explicitly
destroys its window. `eventText` belongs to the selected event and does not
change when the underlying editor changes.

Command-Q and `quit` enqueue one `QUIT`. `nextEvent` returns false after the
queue drains. The process is not forcibly terminated; save and clean up in
Minyar. Closing the last window does not implicitly quit, allowing multiwindow
applications to choose their own policy. The notes example explicitly quits
when its window closes. Quit cancellation and asynchronous sheet dialogs are
not implemented. File dialogs and alerts are modal; an empty path means Cancel.
The application must handle file I/O errors according to Minyar's existing file
API behavior. A standard Edit menu supplies cut/copy/paste, select-all and
undo/redo through AppKit's responder chain.

## Deriving the bridge from Swift

The maintained [Swift probe](../tests/macos-swift-probe.swift) constructs an
NSWindow, sets its title and adds an NSButton. Compile it to inspect the actual
host compiler's output:

```sh
xcrun swiftc -parse-as-library -emit-ir -Onone tests/macos-swift-probe.swift -o build/appkit-probe.ll
rg 'objc_msgSend|initWithContentRect|setTitle:|buttonWithTitle:|addSubview:' build/appkit-probe.ll
```

The output contains Objective-C selectors including
`initWithContentRect:styleMask:backing:defer:`, `setTitle:`,
`buttonWithTitle:target:action:` and `addSubview:`, with `objc_msgSend` dispatch.
Swift's String and ownership operations also appear in that probe. The Minyar
bridge instead converts its UTF-8 Text explicitly and uses the SDK's typed
Objective-C declarations. Clang handles architecture-dependent aggregate
calling conventions (notably NSRect), BOOL, selectors, and ARC. This avoids
assuming Swift's native calling convention or hardcoding message-send casts.

The resulting path is:

```text
Minyar macos function → LLVM C ABI → ARC Objective-C bridge → AppKit
AppKit target/action or delegate → event queue → Minyar event loop
```

This is a public AppKit binding derived from Swift's observable lowering, not a
replacement implementation of AppKit, a Swift compiler, or general SwiftUI
interoperability. It supports the APIs listed above. Arbitrary SDK imports,
Swift generics/closures, WebKit, Metal, accessibility customization,
notifications and document-controller integration are not part of this package.
The separate [experimental SwiftUI compiler target](swiftui.md) explores native
Swift semantics and direct framework imports; it does not use this binding.

References: Apple's [imported C and Objective-C APIs](https://developer.apple.com/documentation/swift/imported-c-and-objective-c-apis),
[NSApplication](https://developer.apple.com/documentation/appkit/nsapplication),
and [event dispatch](https://developer.apple.com/documentation/appkit/nsapplication/nextevent(matching:until:inmode:dequeue:)).

## Verification

Run `make check-macos` in a logged-in macOS desktop session. The suite verifies
Swift selector lowering, actual native target/action and delegate delivery,
multiple windows, destroyed handles, wrong object types, main-thread checks,
Unicode round trips, event snapshots, native sanitizer execution, Minyar scalar
ABI and Text ownership, debug/release builds, all memory profiles, signed app
bundles, and preservation of existing outputs on packaging failures.

`check-macos` is separate from portable/headless gates because it opens native
windows. The Swift probe requires `swiftc` for verification only; application
builds use Clang. Interactive file panels and clipboard behavior need manual
verification; automated tests do not dismiss dialogs or alter your clipboard.
