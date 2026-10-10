# Windows desktop bridge

`windows.min` uses Win32 Unicode controls and Windows messages. Call
`windows.initialize(name)` on the UI thread before other calls. Windows,
containers, controls, menu items and tray icons use generation-checked integer
IDs. Destroying a window invalidates its children and removes their pending
events. An invalid handle or wrong UI thread is a programmer error.

The core API provides windows, rows, columns, padding, labels, buttons, text
fields, checkboxes, fonts, window menus, tray menus and taskbar accessory mode.
Text is checked UTF-8 and converted through the Unicode Windows APIs.
Programmatic text changes do not enqueue user edits. `nextEvent(seconds)` waits
with `MsgWaitForMultipleObjectsEx`; `NONE` means timeout, while `QUIT` is delivered
once before the loop returns false. Actions, edits, close, resize and text-field
Return use the same event constants as the macOS bridge. Edit events carry
copied native text; OS callbacks retain no managed Minyar values. Dispatch is
bounded to 256 Windows messages per iteration, and duplicate pending text edits
are coalesced. Windows dialog keyboard navigation handles Tab between controls.

Windows menu bars belong to a window, so `menu(window, title)` takes the owning
window. `menuItem` currently requires an empty shortcut string. Tray items use
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
- Quiet-time-respecting, silent shell banner notifications. IDs must be closed
  by their owner. Status 1 means the OS accepted the notification, not that it
  was displayed. On Windows 11 these banners are transient, as documented by
  [Microsoft's Shell notification API](https://learn.microsoft.com/en-us/windows/win32/api/shellapi/nf-shellapi-shell_notifyiconw).

Missing OS capabilities and rejected notification input are recoverable error
values. The Linux backend reports unavailable using the same fixed envelopes.
Persistent Action Center toasts, advanced macOS-equivalent controls, menu
accelerators and a unified Windows socket/GUI wait remain subsequent work.

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

`python3 tests/schannel.py` is a separate mandatory Windows CI gate. It tests
native state/buffer/lifetime contracts and compiled Minyar results in debug
and release. An independent OpenSSL peer exercises TLS 1.2/1.3, RSA/ECDSA,
IP names, intermediate chains, one-byte record fragments, bad names, invalid
dates/EKU/critical extensions, unknown CAs, required/absent/untrusted client
identities and truncation after authenticated data. Mutual TLS uses a generated
nonexportable Windows KSP key, exports only its public certificate and removes
both test objects after the peer exits. OS trust stores are never changed.
