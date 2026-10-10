# Desktop release and update delivery

This slice prepares signed releases and provides the Minyar executable-update API.
It creates local artifacts only. It does not create cloud resources, upload to R2,
buy signing certificates, or generate a production update key.

## Release signing

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
state                     # atomically published high-water + active digest
.update-lock              # OS lock; automatically released after process death
versions/<sha256>.bin      # immutable executable generations (.exe on Windows)
```

The previous executable remains available. The bridge fsyncs staged bytes and
containing directories on POSIX and uses committed writes plus write-through
replacement on Windows. The one state file is the activation pointer. A crash
before its replacement leaves the old generation active; a crash after leaves
the complete new generation active. An interrupted write may leave an unused
version or temp file. No updater path executes downloaded bytes.

**Remaining desktop integration:** a launcher must read the active generation
and launch it after process exit, and app bundles/resources require a separate
signed bundle installation strategy. The current API installs one executable;
it does not install a DMG/MSI or update a macOS `.app` bundle in place. Production
key provisioning, R2 deployment, release credentials and launcher/restart wiring
are not completed by this slice.

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
installed version, installed artifact digest and last observed time. A lower
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
Existing coverage and mutation thresholds are unchanged. Real signing,
notarization, Windows execution and online R2 deployment need their respective
host environment and credentials.
