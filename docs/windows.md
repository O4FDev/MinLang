# Windows desktop bridge

`windows.min` uses Win32 Unicode controls and Windows messages. Call
`windows.initialize(name)` on the UI thread before other calls. Windows,
containers, controls, menu items and tray icons use generation-checked integer
IDs. Destroying a window invalidates its children and removes their pending
events. An invalid handle or wrong UI thread is a programmer error.

The core API provides windows, rows, columns, padding, labels, buttons, password
and text fields, multiline editors, read-only text views, checkboxes, sliders,
separators, explicit sizes, enablement, fonts, window menus, tray menus and
taskbar accessory mode.
Text is checked UTF-8 and converted through the Unicode Windows APIs.
Programmatic text changes do not enqueue user edits. `nextEvent(seconds)` waits
with `MsgWaitForMultipleObjectsEx`; `NONE` means no UI event was dispatched, while `QUIT` is delivered
once before the loop returns false. Actions, edits, close, resize and text-field
Return use the same event constants as the macOS bridge. Edit events carry
copied native text; OS callbacks retain no managed Minyar values. Dispatch is
bounded to 256 Windows messages per iteration, and duplicate pending text edits
are coalesced. Windows dialog keyboard navigation handles Tab between controls.
Multiline controls normalize Windows CRLF to LF when returning text. `appendText`
preserves the selection and suppresses programmatic CHANGE events. Text views
have a scrolling viewport; `size` sets it explicitly, and zero removes a dimension
constraint. Sliders require finite increasing ranges and values within them, and
map the range onto one million native trackbar intervals. Endpoints are exact.
The [native trackbar contract](https://learn.microsoft.com/en-us/windows/win32/controls/trackbar-controls)
provides user-driven CHANGE events.

`windows.shareNetworkLoop(loop)` connects an `eventloop` reactor to this same
UI thread. After every `nextEvent` call, consume `eventloop.wait(loop, 0, maximum)`
and handle its socket/timer events on that thread. A network or timer wake
returns `NONE`; it is a readiness hint rather than an application action.
`unshareNetworkLoop()` detaches without closing sockets or the reactor.
Closing an attached reactor detaches before releasing its native resources.

The Windows adapter uses Winsock event registrations and native threadpool
waits to signal one aggregate event. `MsgWaitForMultipleObjectsEx` waits on that
event, GUI messages and the reactor's earliest timer. It does not run a periodic
socket poll, and the GUI wait is not limited to 63 socket handles. `WSAPoll`
remains the owner-thread batch source. Emitted records are rearmed; readiness
for other sockets survives a bounded batch, and consumed stale records settle
to an idle kernel wait. Native callbacks retain only stable native nodes and
signal the aggregate handle. Detachment cancels and joins callbacks before
freeing nodes or event handles. Accepted sockets drop the listener's inherited
event registration before returning to the caller. Ordinary network builds
without the Windows UI package omit all adapter fields and hooks.

The implementation follows Microsoft's [Winsock event semantics](https://learn.microsoft.com/en-us/windows/win32/api/winsock2/nf-winsock2-wsaeventselect),
[threadpool wait lifetime](https://learn.microsoft.com/en-us/windows/win32/api/threadpoolapiset/nf-threadpoolapiset-setthreadpoolwait),
and [GUI wait contract](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-msgwaitformultipleobjectsex).

Windows menu bars belong to a window, so `menu(window, title)` takes the owning
window. Menu shortcuts are scoped to that window: `q` means Ctrl+Q; explicit
Ctrl/Shift/Alt combinations, F1 through F24 and named keys such as Enter are
supported. Duplicate combinations are programmer errors. Tray menus have no
focused window, so their shortcuts must be empty. Destroyed and disabled items
cannot dispatch an accelerator action; IDs are never reused. The message pump
uses [Windows accelerator translation](https://learn.microsoft.com/en-us/windows/win32/learnwin32/accelerator-tables)
before dialog navigation and text-field submission. Tray items use
the application icon; the symbol argument is reserved. Tray notifications use
full 32-bit native IDs and generation-checked public handles; keyboard activation
is enabled. Explorer restart recreates registered icons. `accessory(true)` hides
windows from the taskbar while tray items remain available.

The shared `desktop.min` API supplies these Windows services:

- Battery presence, charge percentage and AC power through `GetSystemPowerStatus`.
- The default IPv4 or IPv6 route and adapter type through IP Helper, plus
  metering through `INetworkCostManager`. Route probes send no packets. If the
  route is known but the cost service is unavailable, `meteringKnown` is false.
- Current-user launch-at-login registration for the current executable. The
  quoted command and registration name identify that executable exactly. An
  existing foreign registration is denied rather than overwritten or removed.
- Persistent Action Center notifications, after explicit Windows app registration
  and initialization described below. Status 1 means the OS accepted a notification,
  not that it was displayed. Disabled OS notification settings return denied.

Missing OS capabilities and rejected notification input are recoverable error
values. The Linux backend reports unavailable using the same fixed envelopes.
The Windows bridge still needs the macOS bridge's richer list, custom drawing,
theme, constraint and file-dialog APIs for complete UI parity.

## Persistent notifications and actions

`winnotify.register(appId, displayName)` creates owned current-user COM,
AppUserModelId and Start Menu entries for the current executable. Use a stable
installation path and unique ASCII app identity. Existing foreign entries are
denied. Call `winnotify.initialize(appId)` on the owning thread on every launch,
including a COM relaunch with `--minyar-toast-activate appId`. Registration alone
does not initialize callbacks. `desktop.notify` shares this initialized provider;
without initialization it returns unavailable.

```minyar
use "winnotify" as notice
use "errors" as errors
let initialized = notice.initialize("com.example.Agent")
if errors.integerOk(initialized) {
    let actions: List<notice.Action> = [notice.action("open","Open agent")]
    let sent = notice.notify("Agent connected","Your device is online.",actions)
    if errors.integerOk(sent) {
        let token = notice.token(errors.integerValue(sent))
        // Persist tokenValue(token) if cancellation is needed after a relaunch.
    }
}
```

Poll the typed `nextAction()` result after `windows.nextEvent`: would-block means
the queue is empty. Native COM callbacks wake the GUI pump and retain no Minyar
values. Each action carries a random 32-character notification token and an
allowlisted action ID. The default body click has action ID `default`. Foreign
app identities, unknown actions, duplicate clicks, expired registrations and
callbacks after cancellation are rejected. Accepted actions are consumed once;
a crash between native queue insertion and application consumption can lose an
action, so this is not a durable message queue.

At most five unique actions are accepted, with bounded UTF-8 labels and escaped
XML. The native queue holds at most 256 actions. At most 1,024 live registrations
persist across restarts, and registrations expire after seven days. Expired
entries and their scoped Action Center records are pruned on initialization and
new delivery. `close(id)` cancels a current native handle; `cancelToken(token)`
also removes a notification after relaunch. `stop()` releases callbacks and
native state while preserving notifications and registration. `unregister()`
clears owned notifications and removes owned installation entries.

The implementation uses Windows' [desktop COM activation contract](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/win32_tile_badge_notif/respond-to-toast-activations)
and [scoped notification history removal](https://learn.microsoft.com/en-us/uwp/api/windows.ui.notifications.toastnotificationhistory.remove).

## Certificate-store private keys

`wincert.findIdentity(fingerprint, "My", false)` selects a certificate by exact
lowercase SHA-256 of its DER in the current-user certificate store. Set the last
argument to true to select the machine store. Stores are opened read-only and
must already exist. Invalid selectors, missing identities and access refusals
return distinct recoverable errors. A successful lookup returns certificate
DER and an opaque local signing reference:

```minyar
use "wincert" as cert
use "tls" as tls
let lookup = cert.findIdentity(deviceFingerprint, "My", false)
if cert.found(lookup) {
    let identity = cert.value(lookup)
    let session = tls.clientWithIdentity(host, randomBytes(64), [],
        [cert.certificate(identity)], cert.signingReference(identity))
}
```

The `MWI1` reference contains only store metadata and the public certificate
fingerprint. It has no pointer or private key bytes. It is a local selector,
not an authorization token, and stops working when the identity is removed.
Signing reopens the selected identity and calls CNG with silent acquisition and
certificate/key matching. Only CNG keys are supported; a provider requiring UI
refuses the operation. The [Windows acquisition contract](https://learn.microsoft.com/en-us/windows/win32/api/wincrypt/nf-wincrypt-cryptacquirecertificateprivatekey)
determines whether the caller owns the native handle, and cleanup follows that
contract. No private-key export function is used. Hardware protection depends
on the certificate's configured key provider; this API does not turn a software
key into a TPM key.

This identity integrates with Minyar's TLS implementation and the `schannel`
package. `schannel.client(host)` uses OS trust roots and SChannel's certificate
validation. `clientWithTrust(host, roots)` requires a nonempty bounded list of
DER roots. `clientWithIdentity(host, roots, identity)` presents the selected
Windows certificate and signs inside its CNG provider; an empty roots list in
that function uses OS roots. Implicit selection of other client identities is
disabled. The explicit-root path additionally checks the complete chain,
hostname, SAN, validity and certificate constraints before exposing plaintext.

The SChannel session is driven by bytes rather than owning a socket. Drain
`takeOutgoing`, deliver those bytes through TCP, feed received ciphertext to
`receive`, and drain authenticated `takeIncoming` bytes. The same API supports
non-blocking sockets and partial records. Call `endInput` on transport EOF: a
missing authenticated TLS `close_notify` returns a truncation error. `shutdown`
queues our close notification; drain it before closing the TCP connection.
`close` always releases native credentials, contexts, keys and buffers, even
after an error. Copies of a closed session return a recoverable closed error.
Each session belongs to the thread that created the provider. TLS 1.2 and 1.3
are supported; older TLS and TLS 1.2 renegotiation are disabled. Queue limits
are one MiB each, and `write` returns would-block before consuming data when
its outgoing queue is full.

SChannel encrypts TLS records over TCP. QUIC uses Minyar's own TLS handshake
driver and opaque CNG signing references because QUIC carries TLS handshake
messages without the TLS record layer. The API follows Microsoft's
[credential configuration](https://learn.microsoft.com/en-us/windows/win32/api/schannel/ns-schannel-sch_credentials),
[post-handshake processing](https://learn.microsoft.com/en-us/windows/win32/secauthn/decryptmessage--schannel),
and [shutdown contract](https://learn.microsoft.com/en-us/windows/win32/secauthn/shutting-down-an-schannel-connection).

## Correctness gate

Run `python3 tests/windows-bridge.py` in native Windows with the MSYS2/UCRT
Clang/lld toolchain. CI runs this gate on every push and pull request.
It creates and removes a nonexportable test CNG key and certificate, verifies
opaque-reference signing and malformed-reference rejection, exercises actual
controls/fonts/layout/menu events and stale handles, and compiles Minyar API
contracts in debug and release. Login tests redirect all writes to a separate
per-process test registry key; OS trust roots are never changed. Explorer tray
lifetime is checked when the Windows test session has a taskbar. The local
Windows 11 desktop VM is required for that check in headless CI environments.
The same gate runs the GUI/socket/timer adapter with 128 concurrent socket
watches, one-event batches, arrival during a real native edit, repeated reads,
accepted-child event isolation, idle timeout settling, timer cancellation and
stale reactor generations. Instrumented `WSAPoll` calls prove the GUI wait
does not poll sockets periodically. Compiled Minyar adapter contracts run in
debug and release.
The control fixture additionally verifies native password/multiline/read-only
styles, Unicode append and line endings, explicit sizing, disabled actions,
trackbar range/endpoints/notifications, accelerator translation and cancellation
after destruction. Invalid sizes, nonfinite or out-of-range slider values, wrong
control kinds, and malformed or duplicate shortcuts must stop with diagnostics.

The notification fixture invokes the real COM activation object from another
thread and parses real WinRT XML. It covers foreign owners/actions, duplicate
clicks, late callbacks, queued-click cancellation, stale handles, expired
registrations, persistent limits across restart and cancellation by token. OS
policy may deny visible banners; XML, COM and persistence contracts remain
mandatory in that case. Debug and release exercise the typed Minyar API too.

`python3 tests/schannel.py` is a separate mandatory Windows CI gate. It tests
native state/buffer/lifetime contracts and compiled Minyar results in debug
and release. An independent OpenSSL peer exercises TLS 1.2/1.3, RSA/ECDSA,
IP names, intermediate chains, one-byte record fragments, bad names, invalid
dates/EKU/critical extensions, unknown CAs, required/absent/untrusted client
identities and truncation after authenticated data. Mutual TLS uses a generated
nonexportable Windows KSP key, exports only its public certificate and removes
both test objects after the peer exits. OS trust stores are never changed.
