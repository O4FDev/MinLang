# Native desktop applications

Minyar describes native views with ordinary functions and values. `ui` holds an
immutable description; `ui-macos` renders it through the existing AppKit bridge.
There is no separate view language and no Swift runtime dependency.

```minyar
use "ui" as ui
use "ui-macos" as app

function view(lights: Integer): ui.View {
    return ui.padded(ui.column([
        ui.heading("A little light in the harbour"),
        ui.label(Text(lights) + " lanterns are shining."),
        ui.button("light", "Light another lantern"),
    ]), 24)
}

app.initialize("Harbour")
let lights = 1
let window = app.open("Harbour", 480, 260, view(lights))
while app.nextEvent(window, 0.25) {
    if app.eventKind(window) == app.ACTION && app.eventKey(window) == "light" {
        lights += 1
        app.update(window, view(lights))
    }
}
app.dispose(window)
```

All AppKit operations run on the main thread. Initialize once before opening
a window. This renderer supports one active window at a time because it owns
the application's native event queue. Closing a window or quitting makes
`nextEvent` return false; `dispose` releases its native controls and may safely
be called again.

`label`, `heading`, `button`, `input`, `toggle`, `row` and `column` compose into
a `ui.View`. Controls have nonempty, unique keys, at most 256 UTF-8 bytes each.
`spaced` and `padded` return new descriptions of rows or columns, with distances
from 0 to 256 points. Lists are copied when entering or leaving a description;
later List edits cannot change an existing tree. `ui.problem(view)` returns an
empty Text for a valid description, or a readable problem. A tree may contain
at most 1,024 view occurrences and 64 levels. The renderer validates before
changing the existing native content.

`app.update` preserves controls when kinds, keys and ordered child structure
stay the same. An input whose text is unchanged keeps its keyboard
focus and selection. It sets changed text and checkbox values in place;
application state remains in your own records.
Changing structure rebuilds all content and ends the previous control handles.
Spacing and padding changes on containers update in place. The low-level
`macos.spacing(stack, points)` also updates existing rows or columns. This first
renderer does not yet reconcile moved controls across structural changes.

An edited input delivers `CHANGE`, its key through `eventKey`, and a copied
text snapshot through `eventText`. Checkboxes and buttons deliver `ACTION`;
read a checkbox with `app.isChecked(window, key)`. Inputs also deliver `SUBMIT`
when Return is pressed. Programmatic value changes do not enqueue user events.
Pass the edited value back into the next description to keep it controlled.

`app.handle(window, key)` and `app.windowHandle(window)` expose checked native
handles for `macos` operations such as accessibility labels, menus and window
autosave. A missing control returns zero. Handles belong to the current native
content and must not be cached across structural updates.

## Build a signed application

On macOS, from a project with `src/main.min`:

```sh
minyar app
minyar app --release --bundle-id org.example.harbour
minyar app --icon assets/Harbour.icns --resources assets/resources
minyar app --release --sign 'Developer ID Application: Example (TEAMID)'
```

The command uses the ordinary project build and dependency lockfile, then
packages `target/debug/NAME.app` or `target/release/NAME.app`. It accepts
`--manifest-path`, `--locked`, `--offline` and `--no-incremental`. The default
bundle ID is `org.minyar.NAME`, replacing underscores with hyphens. Supply a
stable bundle ID for an application you intend to distribute.

The default `--sign -` creates a local ad hoc signature. An explicit identity
selects a certificate already available to `codesign`. The packager verifies
the staged signature before replacing an earlier Minyar-generated bundle;
build or signing errors preserve the previous application. It refuses to
replace unrelated app directories or symlinks. Developer ID notarization,
entitlements and distribution provisioning remain separate release steps.

Try the real Harbour project:

```sh
./minyar app --manifest-path examples/harbour
open examples/harbour/target/debug/harbour.app
```

`examples/gallery/desktop.min` runs the same application as a single file. Its
`--smoke` argument exercises a bounded Unicode/state update and exits for tests.

The rendering API applies descriptions while the process keeps running. Source
watching and hot function replacement belong to the live-programming tools;
this API alone does not reload edited source files.

## Verification

`make check-ui-model` checks the pure model at O0/O2 with ownership assertions.
`make check-application-cli` checks portable command errors and, on macOS, real
debug/release project packaging, resources, signatures and failed-signing rollback.
`make check-ui-macos` needs a logged-in Mac desktop session. It drives actual
AppKit target/action and text delegates at debug/release, checks Unicode,
200 updates retaining control handles, structural rebuilds, closure and the
Harbour gallery and its signed native app bundle. Existing `check-macos` covers the lower-level native bridge
and atomic packager failure paths.
