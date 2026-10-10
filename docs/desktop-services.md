# Desktop services

`desktop` supplies recoverable results for power, network, notifications and
launch at login. Its functions belong to the application's main thread. The
native asynchronous callbacks store only OS objects and C snapshots; managed
Minyar objects are created when the main thread reads a result.

```minyar
use "desktop" as desktop
use "errors" as errors

let power = desktop.power()
if desktop.powerOk(power) {
    let value = desktop.powerValue(power)
    print(desktop.onCharger(value))
    print(desktop.batteryPercent(value))
}
let network = desktop.network()
if desktop.networkOk(network) {
    let value = desktop.networkValue(network)
    if desktop.meteringKnown(value) { print(desktop.metered(value)) }
}
```

Battery percentage is -1 when unavailable. A desktop machine without a battery
is a successful snapshot with `hasBattery` false. Network status describes the
active default path. Wi-Fi, Ethernet, expensive/metered and constrained are
independent flags. Cost can be unknown even when a route is available; check
`meteringKnown` before interpreting a false `metered` value.

On macOS the first `network` call starts Network.framework's path monitor.
Until it produces a snapshot, the result is `wouldBlock`. Changes wake the
AppKit event loop. `networkStop` cancels monitoring; a generation check rejects
late callbacks from an earlier monitor. The next `network` call starts a fresh
monitor. This status is advisory: socket operations still return their own
errors when reachability changes.

`notify(title, body)` returns an owned request ID. `notificationStatus(id)`
reports 0 while pending and 1 when the OS has accepted the request, or a
recoverable denial/system error. Acceptance does not promise visual delivery:
OS permissions and focus settings control that. `notificationClose(id)`
cancels pending delivery, removes delivered notifications and releases the
ID. IDs never reuse; stale IDs return `closed`. The registry is limited to 256
owned requests. Title and body are bounded at 256 and 4096 UTF-8 bytes.

The macOS implementation uses
[UNUserNotificationCenter](https://developer.apple.com/documentation/usernotifications/unusernotificationcenter).
Permission is requested only when the application calls `notify` and the OS
has no decision yet. An unbundled command-line executable returns
`unavailable`; build an application bundle with a stable bundle identifier.
The native test provider exercises denial, deferred permission, cancellation,
late delivery and native failure without changing the test machine's settings.

`launchAtLoginStatus` and `setLaunchAtLogin` return an IntegerResult whose value
is 0 disabled, 1 enabled, 2 requires OS approval, or 3 app not found. On macOS
13 and later they use
[SMAppService](https://developer.apple.com/documentation/servicemanagement/smappservice).
The OS controls approval, and a successful registration can still require
approval. Older systems and unbundled executables return `unavailable`.
These calls operate on the current application; they do not write arbitrary
launch agents.

For a menu-bar application, create `macos.statusItem(title, symbol)` and its
`statusMenu`, then use ordinary menu items. `macos.accessory(true)` hides the
Dock icon while retaining native menu-bar interaction. `statusRemove` is
idempotent and invalidates its owned menu handles and queued events.

Private signing keys use the separate `keychain` package. Its identity contains
a DER public certificate and opaque persistent signer metadata. Security
framework performs signatures without exporting private keys; see
[TLS authentication](tls.md).

Run `tests/desktop-native.py`, `tests/macos-services.py` and
`tests/keychain-native.py` on macOS CI. Native and ASan/UBSan executions are
mandatory there. The tests do not certify production notification delivery or
login registration for an unsigned application; those depend on the final
application bundle and distribution credentials.
