# Install Minyar

The installer and release layout can be exercised locally today. There is no
public release host yet. Once a release operator has prepared and hosted a
signed release directory, installation is one line:

```sh
curl -fsSL https://YOUR-HOST/install | sh
```

The generated installer contains the operator's Ed25519 public key and release
URL. It detects macOS/Linux and Apple silicon/Arm64/Intel/AMD64, verifies the
signed release selection and checksum manifest, then verifies the archive's
SHA-256 before extraction or execution. It installs to `~/.minyar`; set
`MINYAR_HOME` for another location. It does not edit shell startup files.

```sh
export PATH="$HOME/.minyar/bin:$PATH"
minyar new hello
cd hello
minyar run
```

The macOS distribution requires macOS 14+ and Apple's SDK from Xcode or Command
Line Tools. The installer checks the SDK before changing the installation and
prints `xcode-select --install` when it is missing. LLVM is bundled in qualified
macOS archives. See [macOS distributions](macos-distribution.md) for the binary
compatibility and Developer ID/notarization publication gate. SSH release
signatures do not replace Apple's code signing or notarization.

The installer uses POSIX shell, curl, tar, awk, an SHA-256 utility and OpenSSH
`ssh-keygen` with SSH signature verification. It does not require Python, Make
or an existing Minyar installation. Git is needed when downloading Git packages.
Linux artifact names and detection are supported; Linux release archives still
need their own build and platform qualification. A filename alone does not make
a binary portable across libc versions.

## Keep versions together

```sh
minyar self update
minyar toolchain install 0.1.0
minyar toolchain list
minyar toolchain default 0.1.0
minyar toolchain current
```

Installing another toolchain preserves the current default. `self update`
verifies the signed `latest` selection and installs/selects it. When that
version's recorded SHA-256 matches the freshly verified signed manifest, it
selects the existing toolchain without downloading its archive again. Release
metadata is always verified.

Existing versions remain available to running processes and pinned projects.
Installed version directories are immutable: a different archive under an existing version is
rejected. The default and launcher are replaced atomically. A download,
signature, checksum, archive or startup failure preserves the working command.

Put one version in `minyar-toolchain` beside your project's `Minyar.toml` and
commit it:

```text
0.1.0
```

The launcher searches the current directory and its parents. A project pin wins
over the default; `MINYAR_TOOLCHAIN=0.1.0` explicitly overrides both. A missing pin
prints the exact `minyar toolchain install VERSION` command. Selection never
downloads or installs a toolchain implicitly. `toolchain current` explains which
pin, environment setting or default was selected.

```text
~/.minyar/
  bin/minyar             small stable launcher
  manager.sh             version and project-pin selection
  default                default version
  release-key.pub        pinned release signing key
  server                 release URL, stored as data
  toolchains/VERSION/    verified immutable toolchain
  packages/              shared verified source cache
```

The legacy `make install PREFIX=...` source installer remains available and
self-contained. Put the desired installation's `bin` first on PATH.

## Prepare a release locally

The operator needs Python 3.9+, an OpenSSH Ed25519 signing key (or a public key
whose private half is in ssh-agent), and a qualified archive. Private signing
keys must stay outside the public directory. These commands prepare files; they
do not create a host, upload, push or publish anything.

```sh
make package-macos MINYAR_VERSION=0.1.0 \
  MINYAR_LLVM_ROOT="$HOME/.cache/minyar/toolchains/llvm-23.1.2"
python3 install/prepare-release.py \
  --archive build/releases/minyar-0.1.0-macos-arm64.tar.gz \
  --version 0.1.0 \
  --public-key /private/location/releases.pub \
  --signing-key /private/location/releases \
  --server https://YOUR-HOST \
  --output build/public --latest
```

The archive must contain the current `install/install.sh` and
`install/manager.sh`. The macOS packager includes them. Additional supported
architectures can be added to the same version without replacing existing
archives. The preparer verifies the existing checksum manifest's signature
before merging another artifact; altered or unsigned metadata is rejected.
The prepared directory contains:

```text
install
latest
latest.sig
releases/VERSION/SHA256SUMS
releases/VERSION/SHA256SUMS.sig
releases/VERSION/minyar-VERSION-PLATFORM-ARCH.tar.gz
```

Signatures use the `toolchain@minyar` namespace and the `minyar-release` signer
identity. The installer pins the public key and verifies it with
[OpenSSH SSH signatures](https://man.openbsd.org/ssh-keygen#verify).
There is no signature bypass. Key rotation requires a separately reviewed new
bootstrap installer; source templates deliberately fail until a release key is
configured. The signed latest record authenticates selection, while HTTPS
protects bootstrap delivery. This is not a timestamped transparency service.

Use an HTTPS static host for the prepared directory. The [registry guide](registry.md)
describes the layout and local server. For local tests only, a numeric
`http://127.0.0.1:PORT` release URL is accepted.

## Verify locally

```sh
make check-toolchain-install
```

This target generates temporary keys and a loopback artifact server, exercises
the actual `curl ... | sh` flow, installs two fixture toolchains, tests project
pins and updates, and rejects changed signatures/checksums, unsafe archives,
unrelated commands and failed startup. It makes no global installation or
network request outside loopback. The fixture verifies the installation contract;
full macOS binary qualification remains the separate distribution gate.
