# Release signing qualification and owner provisioning

The manual [release-signing workflow](../.github/workflows/release-signing.yml)
creates TEST artifacts and uploads public evidence to the workflow run. It has
only `workflow_dispatch`, `contents: read`, no production secrets, no deployment,
and no public release/R2 publication. The integrator reviews/merges/pushes first
and runs it within the existing free allowance. This work does not authorize paid
runners, new Boat guests, credential purchases, or a public release.

## TEST qualification

`tests/release-pipeline.py` builds one tiny actual native executable, signs a copy
through the explicit TEST modes in `scripts/release.py`, pins the OS signer,
encodes the exact signed tree with `scripts/update-bundle.py`, and signs an
Ed25519 envelope using `scripts/update-manifest.py`. A separate decoder and
OpenSSL verifier consume the bundle/envelope, using the independently derived
public key, fixed signature domain and application/target/channel/origin policy.
The decoded executable is OS-verified again and executed.

Required refusals include wrong OS certificate, wrong Ed25519 key/domain,
signature/metadata/artifact/truncation/resource/executable mutations, and correctly
signed wrong policy metadata. macOS also rejects a changed sealed app resource.
Windows Authenticode seals the executable; the update signature seals its
resources. TEST signing omits timestamps. Production commands still require
Developer ID, accepted notarization, stapling and Gatekeeper on Mac, and SHA256
RFC3161 timestamp plus SignTool `/pa /all /tw` on Windows. The two credential
paths cannot substitute for one another.

The public generation must be a **new `TEST-*` directory**. It becomes visible by
exclusive atomic rename after credential and private staging cleanup. Prior generations are never
replaced, even if the destination is empty or appears during verification. The
optional `--report` writes a new `TEST-*.json` status/cleanup report on runtime
failure too; a guard refusal creates no tools, output, credential directories or
report. Private credentials stay in the temporary stage and never in artifacts.
Any cleanup failure or inventory drift prevents a passing generation. Processes
have closed stdin and bounded timeouts; no password prompt is accepted.
The internal passing report records staging cleanup before publication. An
external report-write failure after publication exits nonzero and explicitly
reports `generationPublished=true`; it never claims that the generation is absent.

### Mac: ephemeral GitHub CI only

Automatic TEST credential creation requires **all** of:

- Explicit `--ephemeral-macos-ci`.
- Actual macOS Python, `GITHUB_ACTIONS=true`, `RUNNER_OS=macOS`, and
  `RUNNER_ENVIRONMENT=github-hosted`.
- Output and temporary credentials beneath the existing `RUNNER_TEMP`.

The credential context repeats the check before any security command. CI uses a
random one-day self-signed TEST certificate/private key, an isolated keychain,
and an admin-domain trust exception scoped to this certificate, code signing
and codesign. `sudo -n` is used only on that disposable runner. Cleanup attempts
trust removal and keychain deletion independently, then compares user/admin
trust and the user keychain search list to the baseline. Failures are reported.
The workflow uses `macos-15`. GitHub distinguishes hosted/self-hosted runners
with these [runner variables](https://docs.github.com/en/actions/reference/workflows-and-actions/variables)
and documents that [hosted runners are destroyed after the job](https://docs.github.com/en/actions/how-tos/deploy/deploy-to-third-party-platforms/sign-xcode-applications).
Environment checks are an operator-context guard, not proof against deliberately
spoofing those variables; never set them on the owner's Mac to bypass refusal.

Exact CI invocation (the workflow resolves its existing OpenSSL 3 installation):

```sh
python3.11 tests/release-pipeline.py --native macos --ephemeral-macos-ci \
  --cc /usr/bin/clang --openssl "$OPENSSL3" \
  --output "$RUNNER_TEMP/TEST-macos-$GITHUB_RUN_ID-$GITHUB_RUN_ATTEMPT" \
  --report "$RUNNER_TEMP/TEST-macos-status-$GITHUB_RUN_ID-$GITHUB_RUN_ATTEMPT.json"
```

Self-signed CI certificates cannot establish Apple notarization, a stapled Apple
ticket, Developer ID distribution or Gatekeeper acceptance. Those remain a
separate production gate with the owner's real credentials. The prior local
certificate attempt was **NONPASS** (`CSSMERR_TP_NOT_TRUSTED` / no identity).
Neither Python mocks nor `codesign -s -` qualify trusted native signing.
The original failed local diagnostic and cleanup inventory are retained;
no cleanup mutation of that prior laptop state is authorized or attempted here.

### OWNER-RUN/CI provisioned TEST identity alternative

An operator can supply an already-provisioned, unlocked keychain containing a
self-signed code-signing-only certificate whose subject/issuer are exactly
`CN=Minyar TEST ONLY <32 lowercase random hex digits>`. The DER and SHA1 pin must
match. This path never creates/imports/unlocks/trusts/deletes OS credentials.
The operator owns provisioning and any eventual cleanup. It is **not permission
for an agent to run trusted signing locally on the owner's Mac**.

```sh
python3.11 tests/release-pipeline.py --native macos \
  --macos-certificate "$TEST_CERT_DER" --macos-thumbprint "$TEST_CERT_SHA1" \
  --macos-keychain "$ALREADY_PROVISIONED_TEST_KEYCHAIN" \
  --cc /usr/bin/clang --openssl "$OPENSSL3" --output "$TEST_OUTPUT_DIRECTORY"
```

On the owner's Mac the agent runs only Python contracts/shipping and, if needed,
ad-hoc `codesign -s -` structure checks. It NEVER runs local sudo (including
`sudo -n`), admin/password/Touch ID operations, keychain creation or cleanup even
temporary, certificate trust changes, TCC/privacy/login/firewall/profiles or
other system security mutations. Prior state permits read-only inventory only,
never cleanup mutations. This development release authorizes no new Mac
security operations. The automatic workflow must stay on disposable CI, never
a self-hosted Mac or a laptop with spoofed CI variables.

```sh
env DYLD_LIBRARY_PATH=/opt/homebrew/opt/expat/lib \
  /opt/homebrew/bin/python3.11 tests/release-signing.py
env DYLD_LIBRARY_PATH=/opt/homebrew/opt/expat/lib \
  /opt/homebrew/bin/python3.11 tests/shipping.py
```

### Windows: exclusive OWN Boat slot

Use actual native Windows Python (`win32`/`nt`), not Mac cross-signing, Wine,
MSYS Python or a borrowed running guest. The owner must finish Windows gates and
hand off the exclusive signing slot on owned Boat `bx_jbb3dmp3` after its base
image/profile transfer. No guest is created/resumed/restarted by this harness.

The workflow runner labels are `[self-hosted, Windows, X64, boat, minyar-signing]`.
Only that owned guest receives them. Its repository variables are absolute paths
`MINYAR_BOAT_PYTHON` (3.11+ native Windows), `MINYAR_BOAT_CLANG` (native linker/SDK
configured), `MINYAR_BOAT_OPENSSL` (OpenSSL 3), `MINYAR_BOAT_SIGNTOOL` (Windows SDK),
and `MINYAR_OWN_BOAT_ID=bx_jbb3dmp3`. Paths are checked, not installed automatically.
Dispatch `windows`/`both` only after setting `windows_gates_complete=true`. The
`minyar-own-boat-windows` concurrency group never cancels an active cleanup run;
external Windows gates still require the owner's slot handoff.

```powershell
$env:MINYAR_OWN_BOAT_ID = 'bx_jbb3dmp3'
& $env:MINYAR_BOAT_PYTHON tests/release-pipeline.py --native windows --owned-boat-windows `
  --cc $env:MINYAR_BOAT_CLANG --openssl $env:MINYAR_BOAT_OPENSSL `
  --signtool $env:MINYAR_BOAT_SIGNTOOL --output 'C:\evidence\TEST-windows-signing' `
  --report 'C:\evidence\TEST-windows-signing-status.json'
if ($LASTEXITCODE -ne 0) { throw 'Native signing or cleanup failed' }
```

The harness records initial CurrentUser `My`/`Root`/`TrustedPublisher` contents,
creates its own short-lived nonexportable CNG code-signing keys/certificates,
and trusts only those TEST certificates. Finally it removes its entries and
private keys and compares every store to its baseline. It does not change
registry settings or machine stores. A changed store/key cleanup failure is a
failed test, not a successful signature. These TEST keys are unrelated to the
hardware/cloud signer needed for production.

## Production: exact owner inputs and commands

Production provisioning below is an **OWNER-RUN checklist**, never an agent
operation on the owner's Mac. Commands are unexecuted reference instructions;
the current development release authorizes none of these laptop operations.
No production credentials are fabricated by the
release tools or TEST workflow. Use a dedicated approved signing environment,
keep private files out of Git/artifacts, and record fingerprints and provider
configuration with the release approval.

### Apple Developer ID and notarization

The owner supplies the exact `Developer ID Application: NAME (TEAMID)` identity,
its `.p12` **with matching private key**, the p12 password, and the required Apple
intermediate certificate chain. An Apple Development identity or a certificate
without its private key cannot satisfy this. Choose a dedicated keychain path,
its password, and a notarization profile name. Owner-run setup, once:

```sh
security create-keychain -p "$SIGNING_KEYCHAIN_PASSWORD" "$SIGNING_KEYCHAIN"
security unlock-keychain -p "$SIGNING_KEYCHAIN_PASSWORD" "$SIGNING_KEYCHAIN"
security import "$DEVELOPER_ID_P12" -k "$SIGNING_KEYCHAIN" \
  -P "$DEVELOPER_ID_P12_PASSWORD" -T /usr/bin/codesign
security import "$APPLE_INTERMEDIATE_CERT" -k "$SIGNING_KEYCHAIN"
security set-key-partition-list -S apple-tool:,apple:,codesign: -s \
  -k "$SIGNING_KEYCHAIN_PASSWORD" "$SIGNING_KEYCHAIN"
security find-identity -v -p codesigning "$SIGNING_KEYCHAIN"
```

Repeat the chain import for each required official Apple intermediate. Check the
identity's SHA1 against the owner's certificate record. Do not add a self-signed
trust override for production. The tools accept explicit keychains and need no
automatic search-list/default-keychain change.

Choose **one** notary credential method. For an App Store Connect team API key,
supply its private `.p8`, key ID and issuer ID:

```sh
xcrun notarytool store-credentials "$NOTARY_PROFILE" \
  --key "$NOTARY_P8" --key-id "$NOTARY_KEY_ID" --issuer "$NOTARY_ISSUER_ID" \
  --keychain "$SIGNING_KEYCHAIN"
```

Or supply Apple ID, Team ID and an app-specific password:

```sh
xcrun notarytool store-credentials "$NOTARY_PROFILE" \
  --apple-id "$NOTARY_APPLE_ID" --team-id "$DEVELOPER_TEAM_ID" \
  --password "$NOTARY_APP_PASSWORD" --keychain "$SIGNING_KEYCHAIN"
```

Do not skip credential validation. These owner commands store credentials and
can contact Apple. [Apple's notarytool migration guide](https://developer.apple.com/documentation/technotes/tn3147-migrating-to-the-latest-notarization-tool)
describes the credential options; [Apple's notarization requirements](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution)
govern production acceptance. An isolated ephemeral production runner can import
the owner's approved p12/chain/profile in the same way, then clean up its own
keychain in `finally`; that is a future authorized production job, not this TEST
workflow.

The owner/integrator's production artifact command is:

```sh
python3.11 scripts/release.py macos --app build/Tolum.app --output dist/Tolum.dmg \
  --identity "$DEVELOPER_ID_IDENTITY" --notary-profile "$NOTARY_PROFILE" \
  --keychain "$SIGNING_KEYCHAIN" --notary-keychain "$SIGNING_KEYCHAIN" \
  --signed-app-output dist/signed-app-tree/Tolum.app
python3.11 scripts/update-bundle.py --root dist/signed-app-tree \
  --output dist/Tolum.mbundle --entrypoint Tolum.app/Contents/MacOS/Tolum \
  --notarized-app Tolum.app
```

The retained app is the exact signed/stapled stage used for the verified DMG.
File-data bundles reject links, resource forks and xattr-only signatures; use
regular-file layouts and reverify the decoded app on the release Mac. The DMG
is a distribution artifact; the custom `.mbundle` is the updater artifact.

### Windows hardware or cloud signer

The owner supplies its publisher certificate and complete chain, a provisioned
hardware-token/HSM/cloud **authentication provider**, the selected certificate's
SHA1 thumbprint, store (`CurrentUser\My` or `LocalMachine\My`), and a tested
**HTTPS RFC3161 TimestampURL**. Configure its CSP/KSP/token middleware and
noninteractive authentication on the owned signing guest. An exportable PFX is
not assumed or requested. A provider that requires interactive approval cannot
silently pass this unattended pipeline.

```powershell
& $env:MINYAR_BOAT_PYTHON scripts/release.py windows --input build\Tolum.exe `
  --output dist\signed-tree\Tolum.exe --signtool $env:MINYAR_BOAT_SIGNTOOL `
  --thumbprint $env:RELEASE_CERT_SHA1 --timestamp $env:RELEASE_TIMESTAMP_URL
# Add --machine-store only for a provisioned LocalMachine\My identity.
if ($LASTEXITCODE -ne 0) { throw 'Production signing failed' }
```

For Azure Artifact Signing the owner instead supplies the existing validated
account/profile, a signing identity with **Artifact Signing Certificate Profile
Signer** role, Windows SDK SignTool, matching-architecture .NET 8 runtime and
`Azure.CodeSigning.Dlib.dll`, plus the client dependencies. A valid regional
endpoint/account/profile JSON file is required. [Microsoft's integration checklist](https://learn.microsoft.com/en-us/azure/artifact-signing/how-to-signing-integrations)
specifies SDK compatibility and matching tool/DLL architectures.

For environment-based service-principal auth, provision `AZURE_TENANT_ID`,
`AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET` through the owner's secret store. These
authenticate Azure, not the code-signing private key. [EnvironmentCredential](https://learn.microsoft.com/en-us/dotnet/api/azure.identity.environmentcredential)
also supports a separate authentication certificate. Restrict the metadata
`ExcludeCredentials` list to disable unwanted fallback providers, especially
`InteractiveBrowserCredential`; do not fall back to an unrelated developer login.

```json
{
  "Endpoint": "https://eus.codesigning.azure.net",
  "CodeSigningAccountName": "OWNER_ACCOUNT",
  "CertificateProfileName": "OWNER_PROFILE",
  "ExcludeCredentials": [
    "ManagedIdentityCredential", "WorkloadIdentityCredential", "SharedTokenCacheCredential",
    "VisualStudioCredential", "VisualStudioCodeCredential", "AzureCliCredential",
    "AzurePowerShellCredential", "AzureDeveloperCliCredential", "InteractiveBrowserCredential"
  ]
}
```

```powershell
& $env:MINYAR_BOAT_PYTHON scripts/release.py windows --input build\Tolum.exe `
  --output dist\signed-tree\Tolum.exe --signtool $env:MINYAR_BOAT_SIGNTOOL `
  --azure-dlib $env:RELEASE_AZURE_DLIB --azure-metadata $env:RELEASE_AZURE_METADATA `
  --timestamp $env:RELEASE_TIMESTAMP_URL
if ($LASTEXITCODE -ne 0) { throw 'Production cloud signing failed' }
```

Microsoft's example timestamp service uses HTTP; this repository deliberately
requires HTTPS. The owner must qualify a provider-supported HTTPS RFC3161 URL
and successful `/tw` verification rather than weakening that policy. Sign every
EXE/DLL in the final tree, copy the resources, and verify all signatures before:

```powershell
& $env:MINYAR_BOAT_PYTHON scripts/update-bundle.py --root dist\signed-tree `
  --output dist\Tolum.mbundle --entrypoint Tolum.exe
if ($LASTEXITCODE -ne 0) { throw 'Bundle preparation failed' }
```

### Ed25519 update key and application policy

The owner supplies the existing encrypted Ed25519 private PEM at `UPDATE_KEY`,
an OpenSSL 3 executable at `OPENSSL3`, and its passphrase in the process environment
`MINYAR_UPDATE_KEY_PASSPHRASE`. Pass the **environment variable name**, not its
value. The update key is separate from Developer ID, Windows signing credentials,
the device mTLS CA/private keys and TLS server keys. The notary `.p8` is another
separate authentication key.

The application must embed the owner's independently verified **32-byte trusted
Ed25519 public key** and app/channel/origin policy in its own compiled release
configuration. `library/update.min` accepts these via `key`, `app`, `target`,
`channel`, `origin` arguments to `inspect`, `install`, `downloadAndInstall` and
`launch`; it contains no global production key. TEST driver keys in
`tests/update-driver.min` and `tests/update-launch-driver.min` are public fixtures
and must never ship as production trust. The generated plan's `publicKeyHex` is
an audit value, not a source of updater trust. Select/document the consuming
application's config file when wiring that app; this repo cannot choose a
production publisher key or application identifier for the owner.

For a consuming app, use `release/update-public-key.hex` as the reviewed public
record and embed that exact value in **that app's** `src/update-policy.min`
before compiling/signing. Keep the private PEM in the owner's secret volume
(for example `/secure/minyar-release/update-signing.pem`, assigned to
`UPDATE_KEY`), never beside the public record. These are explicit wiring
locations for the consuming app, not new production keys in this repository.
Owner-run public-key derivation and format check:

```sh
openssl pkey -in "$UPDATE_KEY" -passin env:MINYAR_UPDATE_KEY_PASSPHRASE \
  -pubout -outform DER -out release/update-public-key.der
python3.11 - <<'PY'
from pathlib import Path
value = Path('release/update-public-key.der').read_bytes()
assert len(value) == 44 and value[:12] == bytes.fromhex('302a300506032b6570032100')
Path('release/update-public-key.hex').write_text(value[12:].hex() + '\n')
PY
```

After comparing that public record to the approved owner key pin, the app's
`src/update-policy.min` calls its updater with literals from the approved policy:

```minyar
use "crypto" as crypto
use "update" as update
// Replace OWNER_APPROVED_64_HEX_DIGITS with the reviewed public record at build time.
let releaseKey = crypto.fromHex("OWNER_APPROVED_64_HEX_DIGITS")
let result = update.downloadAndInstall(updateRoot, releaseKey, "OWNER_APP_IDENTIFIER",
    update.hostTarget(), "stable", "https://OWNER_UPDATE_ORIGIN", now,
    protectedInstallationID, currentVersion)
```

The placeholders must be replaced before shipping; the app supplies its protected
root, time, stable installation ID and current version. Never read the key from
the downloaded envelope/plan. Compare the plan's public key with the compiled
pin as a separate release check.

Every production manifest requires the approved app identifier, actual target,
channel, increasing sequence, version, issued/expiry UTC seconds (at most seven
days apart), rollout and pinned HTTPS origin **as well as** the key. For example,
after the signed bundle above, use owner-set values (Mac shell shown; Windows
uses native Boat Python with the same arguments):

```sh
python3.11 scripts/update-manifest.py --artifact dist/Tolum.mbundle \
  --output dist/release-plan --app "$RELEASE_APP" --target "$RELEASE_TARGET" \
  --channel "$RELEASE_CHANNEL" --sequence "$RELEASE_SEQUENCE" --version "$RELEASE_VERSION" \
  --issued "$RELEASE_ISSUED" --expires "$RELEASE_EXPIRES" --rollout "$RELEASE_ROLLOUT" \
  --origin "$RELEASE_ORIGIN" --key "$UPDATE_KEY" --openssl "$OPENSSL3" \
  --passphrase-env MINYAR_UPDATE_KEY_PASSPHRASE
```

This produces local immutable artifact bytes, channel envelope and
`dist/release-plan/r2-publish-plan.json`. Independently verify the key pin,
metadata, decoded artifact and OS signatures before separate publication
authorization. If publication is later approved, upload the immutable artifact
first and replace the single channel envelope last. No upload/publish command
is part of this workflow or checklist execution by the agent.
