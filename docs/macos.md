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
`org.minyar.application`. `--icon FILE.icns` sets the application icon and
`--resources DIR` copies a directory's contents into `Contents/Resources`, for
example fonts that the application registers with `registerFont`. It is not a
Developer ID distribution or notarization workflow. Entitlements, universal
binaries and App Store packaging are not supplied yet.

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
| Windows | `minimumSize`, `transparentTitlebar`, `autosave`, `capture` | NSWindow, frame autosave |
| Layout | `column`, `row`, `scroll`, `view`, `spacer`, `padding`, `insets`, `size`, `minimumSize`, `maximumSize`, `fill`, `grow`, `align`, `gravity`, `spaceAfter`, `hidden`, `clear`, `remove`, `scrollToTop` | NSStackView, NSScrollView, NSLayoutConstraint |
| Controls | `label`, `button`, `plainButton`, `link`, `textField`, `secureField`, `textEditor`, `textView`, `checkbox`, `slider`, `separator`, `spinner`, `shape` | NSTextField, NSButton, NSSecureTextField, NSTextView/NSScrollView, NSTextView (TextKit 1), NSSlider, NSBox, NSProgressIndicator, NSBezierPath |
| Properties | `text`, `setText`, `appendText`, `enabled`, `checked`, `setChecked`, `value`, `setValue`, `placeholder`, `maxLength`, `focus`, `selectable`, `tooltip`, `accessibilityLabel` | AppKit properties |
| Text input | `plain`, `autoHeight`, `submitOnEnter` | NSTextView delegate |
| Styling | `color`, `background`, `border`, `cornerRadius`, `focusBorder`, `textColor`, `hover`, `font`, `letterSpacing`, `lineHeight`, `lines`, `textAlign`, `symbol` | Dynamic NSColor, CALayer, NSFont/CoreText, SF Symbols |
| Lists | `list`, `addRow`, `rowCount`, `listLine`, `listColors`, `rowButton`, `clickedRow`, `clickedButton` | View-based NSTableView with reused cells |
| Interaction | `clickable`, `draggable` | Tracking areas, window dragging, accessibility press |
| Menus | `menu`, `menuItem`, `menuSeparator` | NSMenu, NSMenuItem, target/action |
| Menu bar | `statusItem`, `statusMenu`, `statusRemove`, `accessory` | NSStatusItem, accessory activation policy |
| Events | `eventType`, `eventSource`, `eventText` | Queued delegate and target/action events |
| System UI | `openFile`, `saveFile`, `alert`, `confirm`, `aboutText`, `showAbout`, `openURL` | NSOpenPanel, NSSavePanel, NSAlert, About panel, NSWorkspace |
| Application | `appearance`, `isDark`, `setting`, `setSetting`, `resource`, `registerFont`, `seconds` | NSAppearance, NSUserDefaults, NSBundle, CTFontManager |
| Clipboard | `clipboardText`, `setClipboardText` | NSPasteboard |

## Building full applications

The Atacama desktop client, a separate project, is a complete application built
with these functions: a header in a transparent title bar, a scrolling playground,
a sidebar, forms, menus and streamed network responses from the
[`http`](../library/http.min) package.

**Layout.** Rows and columns are stack views. `fill` stretches a view across
its parent (rows: down; columns: across) inside the parent's insets, `grow`
gives a view the room left along its parent, and `spacer` adds an empty view
that grows. `maximumSize` caps a filled view, so `align(column, mac.CENTER)`
and a capped, filled child give a centered column of readable width. Views
added to a stack join its START area; `gravity(view, mac.CENTER)` moves one to
the middle, which centers it vertically in a `scroll` view whose content is
shorter than the window. `hidden` views take no space, so pages can share one
scroll view and be switched by hiding the others. Content never resizes its
window: windows keep the size given to `window`, `autosave` or the person.

**Styling.** `color(dark, light, opacity)` makes a color that follows the
application's appearance, so `appearance(mac.DARK)` or `appearance(mac.LIGHT)`
restyles every view without further calls. Fonts are families such as one in a
bundled file registered with `registerFont(resource("fonts/Name.ttf"))`;
variable fonts use the requested weight exactly. Labels wrap with
`lines(label, 0)` and truncate with `lines(label, 1)`.

**Rebuilding content.** Small groups of views are rebuilt with `clear`
followed by new children. `clear` and `remove` end the handles of everything
they remove; keep the new handles to recognise their events.

**Long lists.** A stack of views costs Auto Layout time for every row, and a
rebuild grows faster than the row count: on a 2026 MacBook, rebuilding 200
history rows of three labels and a button took about 1 s, and 800 rows took
10 s. `list` holds rows as text and builds views only for the rows on screen,
so `clear` plus `addRow` for 5,000 rows takes as long as for 50 (about 0.1 s,
mostly laying out the visible rows). Each row has a top, middle and bottom
line, styled for the whole list with `listLine`, and an optional trailing
`rowButton`. A click delivers `ACTION` from the list; `clickedRow` and
`clickedButton` say where. `benchmarks/desktop/history-rows.min` and
`history-list.min` measure both.

**Long, growing text.** A label measures and typesets all of its text again
after every `setText`, so text that grows a little at a time, such as a
streamed answer, costs more with each update, and the total grows with the
square of its length. `textView` is read-only, selectable text that wraps to
its width (give it one with `fill` or `size`) and grows to fit, like a
wrapping label, and `appendText` adds to its end: the text before keeps its
layout, so an append costs about the length of the new text, and a selection
survives it. `appendText` also adds to a `textEditor`. Fonts, colours and line
heights apply as for labels.

**Text input.** `plain` removes an input's own bezel so a styled container can
draw it; `focusBorder` on the container shows focus. Editors can size to their
text with `autoHeight`, and `submitOnEnter` turns Return into `SUBMIT` while
Shift-Return adds a line, as in chat applications. Text fields always enqueue
`SUBMIT` on Return.

**Background work.** A program waiting in `nextEvent` returns early, with
`NONE`, when an `http` request receives data or finishes, so a streamed reply
appears as it arrives without polling quickly. These early returns happen at
most 60 times a second; input events still return at once. A reply streamed
in thousands of small pieces is therefore redrawn once a frame rather than
once a piece: in the Atacama app, a 3,000-piece answer took 2.0 s of CPU time
instead of 6.8 s, with the same final result on screen.

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
when no application event arrived, or when an `http` request makes progress
(at most 60 times a second; see Background work). Zero polls without waiting. Normally use `0.1` to `0.5` to avoid
busy-waiting while keeping application work responsive.

| Kind | Source | Text |
| --- | --- | --- |
| `NONE` | 0 | empty |
| `ACTION` | button, checkbox, menu item, clickable row or column, or a `list` row or row button (`clickedRow`, `clickedButton`) | empty |
| `CHANGE` | text field, editor, or slider | text snapshot for editors; empty for sliders |
| `SUBMIT` | text field, or editor using `submitOnEnter` | text snapshot |
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
undo/redo through AppKit's responder chain. `initialize` also installs the
application menu (About, Hide and Quit) and a Window menu; `menu` places
"File" first, "Help" last and other menus before Window.

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
document-controller integration are not part of this package. Notifications,
login items, power and network status use the separate `desktop` package.
The separate [experimental SwiftUI compiler target](swiftui.md) explores native
Swift semantics and direct framework imports; it does not use this binding.

References: Apple's [imported C and Objective-C APIs](https://developer.apple.com/documentation/swift/imported-c-and-objective-c-apis),
[NSApplication](https://developer.apple.com/documentation/appkit/nsapplication),
and [event dispatch](https://developer.apple.com/documentation/appkit/nsapplication/nextevent(matching:until:inmode:dequeue:)).

## Verification

`macos.shareNetworkLoop(handle)` attaches an `eventloop` reactor to the AppKit
main run loop. It returns an `errors.IntegerResult`; a closed or stale handle
is a recoverable failure. Initialize AppKit first. After `macos.nextEvent`, call
`eventloop.wait(handle, 0, maximum)` or `eventcallbacks.dispatch` with timeout zero
and dispatch callbacks on the main thread. `nextEvent` can return with `NONE`
because network readiness or a timer woke it.

The adapter monitors the reactor's kqueue descriptor with Apple's
[CFFileDescriptor](https://developer.apple.com/documentation/corefoundation/cffiledescriptor)
and schedules the earliest monotonic timer with a reusable
[CFRunLoopTimer](https://developer.apple.com/documentation/corefoundation/cfrunlooptimersetnextfiredate(_:_:)).
Readiness wakes are one-shot until the owner polls; an application that pauses
network dispatch cannot accumulate wake events or spin. No managed reference
or callback crosses a thread. Attaching another loop replaces the previous
attachment. `unshareNetworkLoop` detaches without closing any socket; closing
the attached reactor detaches before its descriptor is reused. The compiler
selects this adapter only when both `macos` and `net` native packages are used.
Ordinary network builds retain their original layout and instructions.

When the program selects the managed graph runtime, `nextEvent` services one
bounded collector batch before waiting. If abandoned cyclic captures still
need work, it pumps AppKit input and returns without sleeping, so the main loop
can dispatch other work and advance another batch. Once that debt drains,
the requested wait sleeps normally; no recurring cleanup timer remains.
This hook is absent from ordinary applications. Native and sanitizer tests
drop a 1,024-node capture cycle without any future network I/O or timers,
check exact reclamation with budgets of one and 32, then check sleeping.

Run `make check-macos` in a logged-in macOS desktop session. The suite verifies
Swift selector lowering, actual native target/action and delegate delivery,
multiple windows, application views (content that never resizes its window,
capped columns, auto-sizing editors, Return to submit, length limits,
clickable rows, appearances and clearing content), destroyed handles, wrong object types, main-thread checks,
Unicode round trips, event snapshots, native sanitizer execution, Minyar scalar
ABI and Text ownership, debug/release builds, all memory profiles, signed app
bundles, and preservation of existing outputs on packaging failures.

`make check-http` runs the `http` package against a local server: status and
headers, Unicode bodies, a character split between streamed packets,
cancellation and connection failures.

`check-macos` is separate from portable/headless gates because it opens native
windows. The Swift probe requires `swiftc` for verification only; application
builds use Clang. Interactive file panels and clipboard behavior need manual
verification; automated tests do not dismiss dialogs or alter your clipboard.
