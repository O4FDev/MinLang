# Desktop release and update delivery

This slice prepares signed releases and provides the Minyar executable and application-bundle update API.
It creates local artifacts only. It does not create cloud resources, upload to R2,
buy signing certificates, or generate a production update key.

## Release signing

The manual artifact-only TEST workflow, CI/Boat guards and exact OWNER-RUN
credential checklist are in [release-signing.md](release-signing.md).

Use Python 3.11 or newer for the release tools. Release signing always copies its
input and replaces the requested output only after every tool succeeds.

```sh
python3 scripts/release.py macos \
  --app build/Tolum.app --output dist/Tolum.dmg \
  --identity 'Developer ID Application: YOUR NAME (TEAMID)' \
  --notary-profile tolum-notary
```

The macOS pipeline signs nested Mach-O code and bundles inside out, with Hardened
Runtime and secure timestamps; verifies the bundle; submits its ZIP through
`notarytool`; checks the explicit `Accepted` status; staples and verifies the app;
creates, signs, notarizes, staples and verifies a compressed DMG. It refuses
Apple Development, ad hoc signing, an absent Keychain notarization profile,
development `get-task-allow` entitlements and bundle symlinks escaping the app.
Provision the Developer ID identity and notarization Keychain profile separately.
The development identity currently present on this workstation cannot distribute
a Developer ID release. [Apple's notarization requirements](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution).

```sh
python3 scripts/release.py windows \
  --input build/Tolum.exe --output dist/Tolum.exe \
  --signtool '/path/to/Windows SDK/signtool.exe' \
  --thumbprint YOUR_40_HEX_DIGIT_CERTIFICATE_THUMBPRINT \
  --timestamp https://YOUR_RFC3161_TIMESTAMP_SERVER
```

Windows signing explicitly selects the certificate from `My`; `--machine-store`
selects the machine store. It uses SHA-256 for Authenticode and the RFC3161
timestamp and verifies `/pa /all /tw`. A SignTool warning, including timestamp
failure, refuses publication. It does not select an arbitrary certificate with
`/a` or accept a private-key password in command arguments.
[SignTool options and exit codes](https://learn.microsoft.com/en-us/windows/win32/seccrypto/signtool).

For an existing Azure Artifact Signing account, replace `--thumbprint` with
`--azure-dlib /path/to/Azure.CodeSigning.Dlib.dll --azure-metadata metadata.json`.
The operator-supplied metadata must name a regional HTTPS
`*.codesigning.azure.net` endpoint without credentials or query parameters,
`CodeSigningAccountName` and `CertificateProfileName`. Existing SDK authentication
handles authorization; the script does not create a subscription or account.
[Microsoft's signing integration](https://learn.microsoft.com/en-us/azure/trusted-signing/how-to-signing-integrations).

Do not buy an EV certificate solely to suppress SmartScreen: Microsoft's current
policy requires reputation to build for new OV and EV binaries alike. Decide the
certificate provider when the actual Windows publisher identity and credentials
are available. [SmartScreen reputation](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation).

## Minyar updater API

Import `use "update" as update`. `update.hostTarget()` returns the compiled OS and
architecture. `update.inspect(...)` performs offline signature and policy checks;
`update.install(...)` authenticates, records the local high-water mark, verifies
artifact bytes and atomically activates an executable generation.
`update.downloadAndInstall(...)` retrieves a single channel envelope and selected
artifact through the portable HTTP backend with OS-root certificate verification.
All these operations return recoverable `errors.Error`/`BooleanResult` values.
Installation also rejects a target differing from the actual host build.

Supply a pinned 32-byte Ed25519 public key, application identifier, channel,
pinned HTTPS origin, trusted current version, Unix UTC time and a stable local
random installation identifier. Store that identifier with protected app data;
do not derive it from identifying hardware or transmit it to the server. The
100 cohorts are SHA-256-derived and stable across releases and promotions;
rollout values 1, 10 and 100 produce nested cohorts.

The root directory must already exist. Use an app-owned directory inaccessible
to other users: on POSIX the native bridge requires the current UID and no group
or world write access; on Windows use an app-owned LocalAppData directory with
its user-only ACL. Windows checks reparse points but does not construct or audit
an ACL. Update handles and calls belong to one thread. Run synchronous downloads
outside UI dispatch callbacks. The bounded HTTP API caps response bytes, TLS
handshake bytes and the complete response-read duration. DNS resolution and the
initial blocking TCP connect still use OS timeouts. Redirects and encoded or
chunked bodies are not decoded; publish raw binary responses with identity
encoding.

An update root contains:

```
state                                   # atomic journal; sole active pointer
.update-lock                            # exclusive OS lock, released on death
versions/<sha256>.bin                    # raw executable (.exe on Windows)
versions/<sha256>.bundle/artifact        # authenticated complete bundle bytes
versions/<sha256>.bundle/payload/        # the exact indexed code/resource tree
versions/<sha256>.<metadatahash>.receipt  # signature + installation metadata
```

`update.launch(root, key, app, target, channel, origin, now, installationID,
currentVersion, arguments)` returns `errors.IntegerResult`: on success its value
is an owned child token, not an OS PID. Arguments are a `List<Text>` excluding
argv[0]; the updater supplies the exact authenticated executable path. Empty
arguments, quotes, backslashes and UTF-8 are preserved. NUL, over 255 arguments,
and more than 32768 encoded argument bytes are errors. `update.wait(token)`
consumes the token once and returns the child's exit status; up to eight children
can await collection. Do not pass tokens to OS process APIs.

`update.restart(...)` has the same arguments. Close application work gracefully
before calling it. It starts a checked successor and exits the calling process
only after process creation/exec succeeds. The successor has a new PID. A failed
restart returns a recoverable error and keeps the current process alive.
Neither API falls back automatically to another generation, a PATH executable,
a mutable symlink, an interpreter, or a shell command. The existing failed-result
value extractors still stop on programmer misuse.

The shipped launcher or application's restart callback must pin its public key,
app/channel/origin, installation ID and trusted current version, then call this
API. A command-line or downloaded manifest must not select these trust anchors.
A target differing from the compiled host, corrupt state, clock rollback, a
lower installed version than the caller's trusted current version, a changed
receipt or artifact, or a device outside the receipt's signed cohort refuses
launch. Observing an unselected/failed newer update preserves the authorization
of the installed generation. Launch verifies that receipt's installed version,
sequence, SHA-256 and size, independently of the newer observation's metadata.

Installed receipts remain valid for offline launch after metadata expiry. Expiry
still blocks every new installation or legacy authorization. Requiring fresh
network metadata for every restart would prevent an offline installed app from
starting. A legacy seven-line v1 journal can still observe newer metadata.
Launching a legacy generation requires fresh signed metadata and the exact
previous artifact through `install`/`downloadAndInstall`; this authenticates a
same-version, same-digest generation and upgrades the journal. There is no
unsigned compatibility fallback.

The journal v2 is nine printable ASCII LF-terminated lines: header
`MINYAR-UPDATER-STATE-2`, highest observed sequence, highest observed version,
observed metadata SHA-256, installed version, installed artifact SHA-256,
last observed UTC time, active metadata SHA-256, and active sequence. The last
two fields identify the installed receipt independently of newer observations
and version bumps reusing identical artifact bytes. A root without an installed
generation has an empty active metadata field and active sequence zero. The
original first seven field positions are preserved.

The bridge stages and commits all bytes before replacing `state`. Bundle
publication creates a complete new directory, publishes it without replacing a
prior directory, then durably stores its separate immutable receipt, and finally
replaces the one journal. POSIX commits files and directories with fsync;
Windows commits files and uses write-through publication. A crash before the
journal changes leaves the previous generation active; after it changes the
complete new generation is active. An uncertain storage error can be checked by
retrying under the lock. Inert `.update-*` files/directories or an unused complete
generation may remain after interruption; the updater never recursively follows
or deletes them. Administrators can remove inactive staging data offline.

Launch holds the updater lock, checks the entire indexed tree, rejects missing
and extra files, symlinks/reparse points, hardlinks and changed file permissions,
and compares all resources and code against the authenticated bundle bytes.
Linux executes the retained checked native image with fexecve. POSIX launch
also resolves the original root through every lexical ancestor and compares it
with the pinned root descriptor, rejecting root/parent renames and substitutions
observed at that check. macOS retains the image descriptor and checks root,
working-directory and executable pathname identities in the child before
replacing it with `posix_spawn(POSIX_SPAWN_SETEXEC)` from its
`.app/Contents/MacOS` location; macOS lacks fexecve.
Windows holds non-write/non-delete shared handles for checked executable and
resource files across verification and CreateProcessW, with an explicit
application path and exact CRT argument quoting. Installation ancestor
directory handles share reads and writes so journal publication can open the
parent for a child rename, but omit delete sharing so ancestors cannot be
renamed or replaced while pinned. The launch directory pins also omit write
sharing. [Microsoft's file sharing contract](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew)
defines the read, write and delete sharing restrictions.
POSIX inherits only non-CLOEXEC standard streams 0/1/2. Linux
uses kernel close_range over the whole descriptor table, keeping only the
CLOEXEC executable and status pipe until exec; this requires Linux 5.9+ with
close_range available in the build headers and permitted by sandbox policy.
Unavailable descriptor cleanup returns a recoverable launch error. Darwin uses
`POSIX_SPAWN_CLOEXEC_DEFAULT` and explicit inheritance actions for standard
streams, so open descriptors above a subsequently lowered RLIMIT_NOFILE are
also excluded. [Apple's spawn interface](https://github.com/apple-oss-distributions/xnu/blob/main/libsyscall/wrappers/spawn/spawn.h)
and [kernel inheritance handling](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/kern/kern_exec.c)
define these platform mechanisms. Windows supplies an explicit handle list for
duplicated standard streams. Update locks, resource handles
and arbitrary application handles are not inherited. POSIX child loader
override variables `LD_*` and `DYLD_*` are removed.

These guarantees assume the documented protected app-owned root. A privileged
or same-user attacker able to chmod/replace the app or its root is outside this
boundary. Retained POSIX descriptors do not prohibit same-user rename or
in-place writes. In particular, Darwin's final identity checks and the subsequent
kernel pathname resolution during SETEXEC are separate operations: a writer can change an ancestor, executable pathname or
checked inode after the checks and before the kernel resolves the launch path.
The deterministic mutation hook exercises changes before the final checks; it
does not prove atomicity across this remaining boundary. macOS launch therefore
requires the protected-root assumption and makes no absolute TOCTOU guarantee.
Call updater APIs from one thread. Application launchers must preserve
the journal during reinstall/recovery and surface refusal instead of silently
running an older generation. No changes to application UI or global launcher
dispatch are made by this updater source slice.

## Complete application bundle format

Use the local encoder, then the existing Ed25519 manifest preparation tool:

```sh
python3 scripts/update-bundle.py \
  --root dist/signed-app-tree --output dist/Tolum.mbundle \
  --entrypoint Tolum.app/Contents/MacOS/Tolum \
  --notarized-app Tolum.app
```

For Windows, prepare a tree with the exact signed executable, signed DLLs and
all resources and use, for example, `--entrypoint Tolum.exe`; omit
`--notarized-app`. Authenticode-sign/verify every executable or DLL before
encoding the final tree. The encoder does not sign, notarize, fabricate a key,
or publish. `--notarized-app` runs real codesign, stapler and Gatekeeper checks
on an actual Mac before output publication. The final custom bundle, rather
than a DMG/MSI/ZIP, becomes `--artifact` for `scripts/update-manifest.py`.

The macOS release pipeline must retain the exact signed, notarized and stapled
staging app used for the verified DMG (the CI owner adds
`--signed-app-output dist/signed-app-tree/Tolum.app`). Encoding the original
unsigned input or an app modified after signing cannot substitute for that
artifact. Actual Developer ID/Authenticode/notarization verification remains
dependent on production credentials. An Ed25519 fixture signature proves only
the updater protocol and never claims production OS signing.

Bundle v1 is deterministic and uncompressed, with no ZIP/tar extraction or
compression bombs. Its binary format is:

- 16 bytes `MINYAR-BUNDLE-1\n`.
- Entry point UTF-8 length (u32 big endian), its bytes, then entry count (u32).
- Each sorted entry: type byte `D` or `F`, executable byte 0 or 1, path length
  (u32), data length (u64), path bytes, then exact file bytes.
- Directories have executable byte and data length zero and must precede their
  children. Every parent directory is explicit; empty directories are preserved.

The encoder compares file identity, type/mode, size, timestamps and attributes
before and after copying and rescans the final directory index before publication.
Windows can expose the transient directory bit `0x10000000` before enumeration
and omit it afterward; only that bit on real directories is normalized.
Readonly/reparse attributes and file identities remain checked. CPython on
Windows derives path execute bits from the filename, and Python 3.12 path
`ctime` reports creation time while descriptor `ctime` reports change time.
The encoder compares the common path/descriptor fields using birth time and
keeps raw descriptor mode/change time checks across the copy; final path modes
remain bound by the rescanned index. See the
[CPython path metadata implementation](https://github.com/python/cpython/blob/v3.12.10/Modules/posixmodule.c)
and [descriptor metadata implementation](https://github.com/python/cpython/blob/v3.12.10/Python/fileutils.c).
Output temporaries are closed before replacement and failure cleanup on Windows.

The whole artifact, including the index and entry point, is bound by the
existing signed size/SHA-256. At most 4096 entries and 128 MiB including the index
are allowed. Paths are portable ASCII relative paths, at most 512 bytes with
components up to 64 bytes. The encoder/parser reject dot components, absolute
paths, control bytes, Windows streams/reserved device names, trailing dot/space
aliases and case-insensitive duplicates. Entry points must be executable regular
native host images. Files are published read-only (0444 data, 0555 code on POSIX).

Bundle v1 supports complete regular-file `.app`/Windows trees, including
Info.plist, signature/ticket files, nested code and all indexed resources. It
deliberately rejects symlink framework layouts, including the usual
`Foo.framework/Versions/Current` and top-level framework aliases, even when their
targets remain inside the app. This is a supported resource-bundle scope, not a
general transport for arbitrary existing macOS apps. It also rejects hardlinks,
non-ASCII filenames, special files, xattr-only code signatures and resource forks.
Build a compatible regular-file layout before signing; do not dereference,
flatten or modify an already signed framework after notarization. The encoder
does not offer a safe-dereference mode. Extended attributes are not transported.
The signed package authenticates the exact directory index, executable modes
and file bytes, and launch verifies the complete reconstructed tree. Production
platform checks must additionally validate the final reconstructed
signed/stapled tree with real platform tools and credentials.

## Signed wire format and rollback protection

A channel object is exactly a 64-byte detached Ed25519 signature followed by
1..4096 bytes of metadata. Sign the byte prefix
`MINYAR-UPDATE-SIGNATURE-V1\0` plus the metadata, with no JSON reserialization.
Metadata is exactly these twelve printable ASCII lines, each terminated by LF:

```
MINYAR-UPDATE-1
org.tolum.peer
windows-x86_64
stable
42
1.2.3
1800000000
1800003600
1
https://updates.example/releases/<lowercase-sha256>/Tolum.exe
<lowercase-sha256>
12345
```

No blank, extra, CR, NUL or non-ASCII field is accepted. Integers are canonical
unsigned decimal with no leading zero; versions have exactly three canonical
numeric components. Sequences range from 1 to 2147483647 and must increase for
metadata changes, including a rollout promotion. Expiry must exceed trusted
current time, issuance allows at most 300 seconds of forward skew, and the
validity interval cannot exceed seven days. Artifacts are 1..128 MiB. Their URL
must exactly match the pinned origin and content-addressed release path, with
one safe ASCII filename; signatures bind its size and SHA-256.

The protected state records highest sequence, highest version, metadata hash,
installed version, installed artifact digest, last observed time and the active receipt identity. A lower
sequence, lower version, altered metadata at the same sequence, corrupt state or
clock rollback fails closed. Identical metadata may be retried after a failed
artifact download. Valid newer metadata records its high-water mark before
artifact download, even when the device is outside the cohort; a failed download
cannot enable replay of an older release. Refusing downgraded or corrupt state
never automatically deletes the high-water mark. Reinstalling after local state
loss must preserve the current trusted version and use a current channel; a
privileged attacker able to replace the application or its state is outside this
boundary.

The rollback, freeze and mixed-metadata tests draw from the
[TUF threat model and specification](https://theupdateframework.github.io/specification/v1.0.36/).
This is a single pinned-key protocol, not a full TUF repository with threshold
roles or online key rotation. Key compromise needs a separately authenticated
key replacement mechanism. Native Ed25519 verification uses unmodified
[Monocypher 4.0.3](https://monocypher.org/changelog), pinned and attributed in
`vendor/README.md`; signing test seeds are public RFC 8032 fixtures only.

## Prepare static R2 objects

Use an existing offline Ed25519 key and OpenSSL 3:

```sh
python3 scripts/update-manifest.py \
  --artifact dist/Tolum.exe --output dist/r2 \
  --app org.tolum.peer --target windows-x86_64 --channel stable \
  --sequence 42 --version 1.2.3 --issued 1800000000 --expires 1800003600 \
  --rollout 1 --origin https://updates.example \
  --key /secure/offline-ed25519.pem
```

The origin uses the exact ASCII `https://` prefix, a host and an optional port
from 1 to 65535. Credentials, whitespace, control bytes, paths and query or
fragment delimiters are rejected before signing or writing output, including
empty `?` and `#` suffixes. Valid host casing and explicit HTTPS ports are
preserved in the signed URL.

`--passphrase-env NAME` asks OpenSSL to read an existing environment variable;
the tool never places its value in an argument. It validates the Ed25519 public
key format, signs and independently self-verifies the signature, rechecks copied
artifact bytes and creates `r2-publish-plan.json` plus:

```
releases/<sha256>/Tolum.exe
channels/stable/windows-x86_64.update
```

Publish the immutable artifact first and the single envelope last. Immutable
objects carry `public, max-age=31536000, immutable`; channel pointers carry
`no-store`. Promote the same version from 1 to 10 to 100 by issuing new signed
metadata with a strictly greater sequence each time. Configure a production R2
custom domain and an explicit cache bypass for `channels/*`; do not override the
pointer policy with a broad cache rule. `r2.dev` is intended for development and
does not provide the custom-domain cache behavior. No upload command is executed
here. [Cloudflare R2 cache integration](https://developers.cloudflare.com/cache/interaction-cloudflare-products/r2/).

## Tests

`make check-shipping` runs release failure injection, offline publication,
RFC 8032 known-answer and signature/key mutations, native ASan/UBSan checks,
OS lock and path checks, process-death fault injection around every publication
boundary, compiled Minyar adversarial policy and cohort tests, and a hostile
bounded HTTP peer. The same gate is included in `check` and `check-portable`.
Existing coverage and mutation thresholds are unchanged. New gates are `tests/update-bundle.py`, `tests/update-launch.py` and
`tests/update-launch-native.py`; the CI owner registers them globally. They use
locally built owned helper images signed with the public fixture key, exact argv
and resource checks (native CFBundle lookup on macOS), fresh legacy authorization,
installed receipt expiry/cohort/version checks, independent malicious binary
indexes, deterministic post-check mutation races, real writer lock contention,
and abrupt death during every bundle/receipt/journal publication phase.
Native cleanup runs under ASan/UBSan on supported POSIX hosts. Actual Windows and
macOS provider results must be recorded separately from Linux; an unavailable
provider is not a passing mock. Production signing/notarization and R2 deployment
require the respective host credentials and operator provisioning.

Packager link fixtures check their actual `lstat`/readlink identity, hardlink
inode/link counts and FIFO type before testing rejection. MSYS2 defaults to
deep copies when asked to create a symlink; these copies are valid regular
resources and have a separate positive control. On MSYS/Cygwin the link fixture
starts a fresh interpreter with `winsymlinks:sys` to create a recognized POSIX
link without native symlink privileges. This proves that provider's link
rejection; native Windows reparse results remain separate.
[MSYS2 link modes](https://www.msys2.org/docs/symlinks/)
and [Cygwin symbolic links](https://cygwin.com/cygwin-ug-net/using.html#pathnames-symlinks)
describe these representations.

The Linux public process-failure fixture deliberately sets RLIMIT_NPROC to zero
in an owned driver subprocess. LeakSanitizer also needs a tracing process, so
that restricted subprocess alone uses `detect_leaks=0` while ASan/UBSan remain
enabled and all Result/journal/caller-survival assertions remain unchanged. The
native fork-failure fixture restores the limit before exit, checks exact
descriptor cleanup and runs with LeakSanitizer enabled.
