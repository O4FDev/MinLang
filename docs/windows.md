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

This identity integrates with Minyar's TLS implementation. The separate
SChannel transport and its client-certificate API are not included in this
core bridge slice.

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
