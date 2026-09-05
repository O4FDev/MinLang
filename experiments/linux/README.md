# Linux correctness validation

Use `scripts/check-linux.py` on Linux aarch64 or x86_64 to build from source
and run compiler, runtime, and sanitizer checks. It excludes performance tests.

## Run on a Linux host

Install Clang, its sanitizer runtime, lld, make, Python 3, zsh and the system C/C++
development headers. The Dockerfile below records the Ubuntu 24.04 package set
used for these checks. From the project root:

```sh
python3 scripts/check-linux.py --source "$PWD" --output-dir "$PWD/build/linux-validation/native"
```

The runner requires an aarch64 or x86_64 Linux host, selects lld for linking, and
builds its own compiler/runtime artifacts. It does not reuse binaries from the
source checkout. Use `--clang` and `--cxx` to select alternative compiler paths,
or `--timeout 3600` to increase the timeout for each top-level check.
`--dry-run` prints the planned checks without building anything and also works
on macOS.

## Run in a container

Build the image and keep its ID alongside the results:

```sh
mkdir -p build/linux-validation/arm64
docker build --platform linux/arm64 -f experiments/linux/Dockerfile -t minyar-linux-arm64 .
docker image inspect minyar-linux-arm64 --format '{{.Id}}' > build/linux-validation/arm64/image-id.txt
docker run --rm --platform linux/arm64 -v "$PWD:/work" -w /work minyar-linux-arm64 \
  python3 scripts/check-linux.py --source /work --output-dir /work/build/linux-validation/arm64
```

For x86_64, build a separate image using `--platform linux/amd64`, tag it
`minyar-linux-amd64`, and use a separate output directory such as
`build/linux-validation/amd64`. Use the same platform flag when running it.
Docker needs an appropriate native host or configured architecture emulation.
Retain the image ID and Clang version when comparing runs.

## Resume and inspect evidence

Each execution prints its retained `minyar-linux-...` directory. It contains
`results.json`, per-check logs, a source snapshot with hashes, runner versions,
and nested profile/critical-path evidence. To resume an interrupted or corrected
run inside the same image, replace `RUN_DIRECTORY` with that printed directory:

```sh
docker run --rm --platform linux/arm64 -v "$PWD:/work" -w /work minyar-linux-arm64 \
  python3 scripts/check-linux.py --resume /work/build/linux-validation/arm64/RUN_DIRECTORY
```

On a native Linux host, pass the same `--resume` option directly to Python.
Resume verifies the source hashes, architecture and tool paths. Successful
checks with matching commands and environments can be reused; changed checks
run again. Previous reports are kept under `history/`, and failed checks remain
in the evidence. Start a new run when compiler or runtime sources change.

## Optional runtime leak checks

After a successful main run, replay its normal-exit runtime fixtures with
LeakSanitizer enabled, using the same Linux environment and architecture:

```sh
python3 scripts/check-linux-leaks.py --run-dir /path/to/minyar-linux-RUN
```

For containers, run that command inside the matching image with the retained
run mounted at its original path, as in the resume example. A deliberately leaked
allocation must first trigger the detector; then the eager-runtime and completed
system-allocator fixtures must exit without leaks. Compiler processes are
excluded because their arena intentionally lasts until process exit. Results,
logs and executable hashes are retained in a new `leaks-...` directory inside
the original run.
